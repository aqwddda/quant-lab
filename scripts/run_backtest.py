"""Run from frozen local data, verify provenance, and write auditable reports."""
import argparse
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.cache' / 'matplotlib'))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import yaml
from src.backtest import run_backtest
from src.data.manifest import file_sha256
from src.data.loader import load_bars
from src.data.store import DataStore
from src.execution import Costs
from src.metrics import calculate_metrics
from src.validation import future_mutation_test


def read_config(path, expected):
    with path.open() as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict) or set(config) != set(expected):
        raise ValueError(f'{path}: keys must be {sorted(expected)}')
    return config


def write_reports(result, report, output):
    output.mkdir(parents=True, exist_ok=True)
    equity = result.equity.copy()
    equity['benchmark_equity'] = result.benchmark_equity.equity
    equity['benchmark_daily_return'] = result.benchmark_equity.daily_return
    equity['benchmark_drawdown'] = result.benchmark_equity.drawdown
    equity.to_csv(output / 'equity.csv', index=False, float_format='%.15g')
    result.trades.to_csv(output / 'trades.csv', index=False, float_format='%.15g')
    result.benchmark_trades.to_csv(output / 'benchmark_trades.csv', index=False, float_format='%.15g')
    result.benchmark_equity.to_csv(output / 'benchmark_equity.csv', index=False, float_format='%.15g')
    with (output / 'metrics.json').open('w') as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False, allow_nan=False)
    strategy = report['audit']['strategy_config']
    currency = report['audit']['currency']
    for filename, column, ylabel, multiplier in [
        ('equity_curve.png', 'equity', f'Equity ({currency})', 1),
        ('drawdown.png', 'drawdown', 'Drawdown (%)', 100),
    ]:
        fig, ax = plt.subplots(figsize=(11, 5), layout='constrained')
        ax.plot(result.equity.date, result.equity[column] * multiplier,
                label=f"{strategy['symbol']} SMA {strategy['fast_window']}/{strategy['slow_window']}")
        ax.plot(result.benchmark_equity.date, result.benchmark_equity[column] * multiplier,
                label=f"{strategy['symbol']} buy & hold", alpha=0.8)
        ax.set(xlabel='Exchange session date', ylabel=ylabel,
               title=f"Net of commission and slippage; {strategy['price_basis']} OHLC")
        ax.legend()
        ax.grid(alpha=0.25)
        fig.savefig(output / filename, dpi=150)
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strategy-config', type=Path, default=ROOT / 'config/strategy.yaml')
    parser.add_argument('--backtest-config', type=Path, default=ROOT / 'config/backtest.yaml')
    parser.add_argument('--data-config', type=Path, default=ROOT / 'config/data.yaml')
    parser.add_argument('--data-root', type=Path, default=ROOT)
    parser.add_argument('--dataset-id', help='Explicit frozen version (required when ambiguous)')
    args = parser.parse_args()
    strategy = read_config(args.strategy_config, ['symbol', 'market', 'price_basis', 'fast_window', 'slow_window'])
    config = read_config(args.backtest_config, [
        'initial_cash', 'commission_rate', 'slippage_rate', 'start_date', 'end_date',
        'reports_dir', 'annualization_factor', 'risk_free_rate',
    ])
    store = DataStore.from_config(args.data_config, args.data_root)
    data = load_bars(strategy['market'], [strategy['symbol']], config['start_date'], config['end_date'],
                     price_basis=strategy['price_basis'], store=store, dataset_id=args.dataset_id)
    manifests = data.attrs['manifests']
    manifest = manifests[0]
    checksum = manifest['normalized_sha256']
    # Fail on truncated date-range downloads rather than imply a full experiment.
    if (data.date.iloc[0] - pd.Timestamp(config['start_date'])).days > 7 or (pd.Timestamp(config['end_date']) - data.date.iloc[-1]).days > 7:
        raise ValueError('Dataset does not cover requested experiment range')
    if len(data) <= strategy['slow_window']:
        raise ValueError('Require at least one eligible execution session')
    cutoffs = sorted(set([strategy['slow_window'] - 1, len(data) // 2, len(data) - 2]))
    for cutoff in cutoffs:
        future_mutation_test(data, data.date.iloc[cutoff], strategy['fast_window'], strategy['slow_window'])
    result = run_backtest(data, strategy['fast_window'], strategy['slow_window'],
                          config['initial_cash'], Costs(config['commission_rate'], config['slippage_rate']),
                          strategy['symbol'])
    for item in manifests:
        if item['schema_version'] == 2:
            if store.load_manifest(item['dataset_id']) != item:
                raise ValueError('Dataset manifest changed during the run')
            store.verify(item)
        else:
            for entry in item['normalized_files'].values():
                if file_sha256(entry['path']) != entry['sha256']:
                    raise ValueError('Data file changed during the run')
            entry = item['metadata_file']
            if file_sha256(entry['path']) != entry['sha256']:
                raise ValueError('Dataset metadata changed during the run')
    adjusted = strategy['price_basis'] != 'raw'
    assumptions = [
        'Signal at T close; fill at next available session open, never at T close.',
        'Integer shares, all cash allocation, no interest, borrowing, taxes or minimum fees.',
        'Slippage is embedded in execution_price and never deducted twice.',
        'No end-date liquidation; final holdings marked at selected-basis close.',
        f"Benchmark buys once at first eligible open (session {strategy['slow_window'] + 1}) with identical costs and initial cash.",
        'Metrics include warmup cash sessions; CAGR uses calendar years, volatility/Sharpe use configured sessions/year.',
        'Trade count counts fills; win rate, profit factor and holding days use closed round trips only.',
        'Sortino uses RMS negative excess returns over all sessions; turnover is gross traded value / mean equity, not annualized.',
        'Undefined ratios are JSON null, including profit factor when there are no losses.',
    ]
    assumptions += manifest.get('assumptions', [])
    if adjusted:
        assumptions += ['Synthetic adjusted-price account: signals, fills and valuation use the same selected adjusted basis.',
                        'Integer synthetic adjusted shares; no separate dividend cash flows or share changes.']
    else:
        assumptions += ['Raw-price research smoke test: corporate action cash flows and share changes are not modeled.']
    if strategy['market'] == 'CN':
        assumptions += ['This backtest does not yet model all China A-share market-specific execution rules.']
    currency = 'CNY' if strategy['market'] == 'CN' else 'USD'
    report = {
        'strategy': calculate_metrics(result.equity, result.trades, config['initial_cash'],
                                      config['annualization_factor'], config['risk_free_rate']),
        'benchmark': calculate_metrics(result.benchmark_equity, result.benchmark_trades, config['initial_cash'],
                                       config['annualization_factor'], config['risk_free_rate']),
        'audit': {
            'strategy_config': strategy, 'backtest_config': config, 'data_sha256': checksum,
            'data_provenance': manifest, 'manifest': manifest,
            'market': strategy['market'], 'provider': manifest['provider'],
            'price_basis': strategy['price_basis'], 'dataset_id': manifest['dataset_id'], 'currency': currency,
            'data_storage': {'root': str(store.root), **store.storage},
            'manifest_sha256': file_sha256(store.manifest_path(manifest['dataset_id'])) if manifest['schema_version'] == 2 else manifest['metadata_file']['sha256'],
            'actual_start': str(data.date.iloc[0].date()),
            'actual_end': str(data.date.iloc[-1].date()), 'rows': len(data),
            'future_mutation_test_passed': True,
            'future_mutation_cutoffs': [str(data.date.iloc[i].date()) for i in cutoffs],
            'python_version': platform.python_version(),
            'package_versions': {name: version(name) for name in ['pandas', 'numpy', 'pyarrow', 'PyYAML', 'matplotlib']},
            'source_sha256': {str(p.relative_to(ROOT)): file_sha256(p)
                              for directory in ['src', 'scripts'] for p in sorted((ROOT / directory).rglob('*.py'))},
            'assumptions': assumptions,
        },
    }
    write_reports(result, report, ROOT / config['reports_dir'])
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
