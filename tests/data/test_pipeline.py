import json
from pathlib import Path
import subprocess
import sys
import pandas as pd
import pytest
from scripts.download_data import download_dataset
from src.data.providers.yahoo import YahooProvider
from src.data.providers.tushare import TushareProvider
from src.data.loader import load_bars
from tests.data.test_yahoo_provider import FakeYahoo
from tests.data.test_tushare_provider import FakeTushare

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('provider,market,symbol', [('yahoo', 'US', 'SPY'), ('yahoo', 'US', 'AAPL'),
                                                 ('tushare', 'CN', '000001.SZ'), ('tushare', 'CN', '600519.SH')])
def test_four_symbol_download_freeze_verify_load(monkeypatch, store, provider, market, symbol):
    monkeypatch.setenv('TUSHARE_TOKEN', 'fixture-token')
    if provider == 'yahoo':
        transport = YahooProvider(client=FakeYahoo())
        start, end, basis = '2020-08-28', '2020-08-31', 'provider_adjusted'
    else:
        transport = TushareProvider(client=FakeTushare(symbol))
        start, end, basis = '2020-01-02', '2020-01-03', 'qfq'
    manifest = download_dataset(provider, market, symbol, start, end, store=store,
                                 dataset_id=f'{provider}_{symbol}_pipeline', provider_instance=transport)
    store.verify(store.load_manifest(manifest['dataset_id']))
    data = load_bars(market, [symbol], start, end, price_basis=basis, store=store)
    assert len(data) == 2 and data.symbol.eq(symbol).all()
    source = pd.read_parquet(store.resolve(manifest['source_files']['bars']['path']))
    pd.testing.assert_frame_equal(source, transport.source_frames['bars'])
    with pytest.raises(FileExistsError):
        download_dataset(provider, market, symbol, start, end, store=store,
                           dataset_id=manifest['dataset_id'], provider_instance=transport)
    for tool in ['verify_dataset.py', 'inspect_data.py']:
        process = subprocess.run([sys.executable, str(ROOT / 'scripts' / tool), '--root', str(store.root),
                                  '--dataset-id', manifest['dataset_id']], capture_output=True, text=True)
        assert process.returncode == 0, process.stderr
        assert manifest['dataset_id'] in process.stdout


def test_failed_normalization_keeps_source_without_publishing(store):
    class InvalidProvider(YahooProvider):
        def fetch_snapshot(self, *args, **kwargs):
            snapshot = super().fetch_snapshot(*args, **kwargs)
            for frame in [snapshot.prepared['bars'], snapshot.source_frames['bars']]:
                frame['Volume'] = 1000.5
            return snapshot
    with pytest.raises(ValueError, match='integer-valued'):
        download_dataset('yahoo', 'US', 'AAPL', '2020-08-28', '2020-08-31', store=store,
                         dataset_id='failed_source', provider_instance=InvalidProvider(client=FakeYahoo()))
    assert store.resolve('data/source/yahoo/failed_source/bars.parquet').is_file()
    assert not store.manifest_path('failed_source').exists()


def test_verify_cli_returns_failure_on_corruption(store, saved):
    path = store.resolve(saved['normalized_files']['bars']['path'])
    with path.open('ab') as handle:
        handle.write(b'corruption')
    process = subprocess.run([sys.executable, str(ROOT / 'scripts/verify_dataset.py'), '--root', str(store.root),
                              '--dataset-id', saved['dataset_id']], capture_output=True, text=True)
    assert process.returncode == 1 and 'FAIL' in process.stderr


@pytest.mark.parametrize('market,symbol', [('US', 'AAPL'), ('CN', '000001.SZ')])
def test_generic_report_and_backtest_never_import_provider_sdks(store, saved, canonical, tmp_path, market, symbol):
    import yaml
    if market == 'CN':
        canonical['symbol'] = symbol
        saved = store.save_dataset(canonical, dataset_id='fixture_CN', provider='fixture', provider_version='1',
            market=market, asset_type='EQUITY', start='2020-01-01', end=str(canonical.date.iloc[-1].date()),
            source_frames={'bars': canonical})
    strategy = tmp_path / 'strategy.yaml'
    strategy.write_text(yaml.safe_dump({'symbol': symbol, 'market': market, 'price_basis': 'raw',
                                        'fast_window': 20, 'slow_window': 60}))
    config = yaml.safe_load((ROOT / 'config/backtest.yaml').read_text())
    config.update({'start_date': saved['requested_start'], 'end_date': saved['requested_end_inclusive'],
                   'reports_dir': str(tmp_path / 'reports')})
    backtest = tmp_path / 'backtest.yaml'
    backtest.write_text(yaml.safe_dump(config))
    code = """
import builtins, runpy, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'yfinance', 'tushare'} or name.startswith('src.data.providers'):
        raise AssertionError('Backtest imported a provider/SDK: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
script = sys.argv[1]
sys.argv = sys.argv[1:]
runpy.run_path(script, run_name='__main__')
"""
    process = subprocess.run([sys.executable, '-c', code, str(ROOT / 'scripts/run_backtest.py'),
        '--strategy-config', str(strategy), '--backtest-config', str(backtest), '--data-root', str(store.root)],
        capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    report = json.loads((tmp_path / 'reports/metrics.json').read_text())
    assert report['audit']['price_basis'] == 'raw'
    assert report['audit']['dataset_id'] == saved['dataset_id']
    assert report['audit']['strategy_config']['symbol'] == symbol
    if market == 'CN':
        assert 'This backtest does not yet model all China A-share market-specific execution rules.' in report['audit']['assumptions']
    for name in ['trades.csv', 'equity.csv', 'metrics.json', 'equity_curve.png', 'drawdown.png']:
        assert (tmp_path / 'reports' / name).is_file()
