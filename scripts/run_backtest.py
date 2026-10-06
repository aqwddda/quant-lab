"""Run from frozen local data, verify provenance, and write auditable reports."""
import argparse
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.cache' / 'matplotlib'))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import yaml
from quant_lab.backtest.legacy import run_backtest
from quant_lab.data.manifest import file_sha256
from quant_lab.data.loader import load_bars, load_dataset, iter_bars
from quant_lab.data.store import DataStore
from quant_lab.backtest.execution import Costs
from quant_lab.backtest.metrics import calculate_metrics
from quant_lab.validation import future_mutation_test


def read_config(path, expected):
    with path.open() as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict) or set(config) != set(expected):
        raise ValueError(f'{path}: keys must be {sorted(expected)}')
    return config



def resolve_strategy_config(config):
    """Accept historical experiments; new configurations separate strategy/data."""
    legacy = {'symbol','market','price_basis','fast_window','slow_window'}
    if set(config) == legacy:
        return dict(config), config
    if set(config) not in ({'strategy','data'},{'strategy','data','chan'}) or set(config['strategy']) != {'name','params'}:
        raise ValueError('Require strategy{name,params} and data configuration')
    from quant_lab.market import AssetClass, Timeframe
    data = config['data']
    if not {'symbol','asset_class','timeframe','price_basis'}.issubset(data):
        raise ValueError('Data requires symbol, asset_class, timeframe, price_basis')
    if set(data) - {'symbol','asset_class','timeframe','price_basis','market','venue','session_timezone'}:
        raise ValueError('Unknown data configuration keys')
    AssetClass(data['asset_class'])
    Timeframe.parse(data['timeframe'])
    if config['strategy']['name'] == 'chan_fx':
        if config['strategy']['params'] or set(config.get('chan',{})) - {'initial_direction_policy'}:
            raise ValueError('Chan-FX has no trading params; only initial_direction_policy is configurable')
        return {**data,'name':'chan_fx','chan':config.get('chan',{})}, config
    if 'chan' in config or config['strategy']['name'] != 'sma_cross':
        raise NotImplementedError('Trading rules are implemented only for sma_cross')
    params = config['strategy']['params']
    if set(params) != {'fast_window','slow_window'}:
        raise ValueError('sma_cross requires fast_window and slow_window')
    resolved = {**data, **params, 'market': data.get('market','US')}
    return resolved, config

def write_reports(result, report, output):
    output.mkdir(parents=True, exist_ok=True)
    equity = result.equity.copy()
    equity['benchmark_equity'] = result.benchmark_equity.equity
    return_column = 'daily_return' if 'daily_return' in result.equity else 'bar_return'
    equity['benchmark_' + return_column] = result.benchmark_equity[return_column]
    equity['benchmark_drawdown'] = result.benchmark_equity.drawdown
    equity.to_csv(output / 'equity.csv', index=False, float_format='%.15g')
    result.trades.to_csv(output / 'trades.csv', index=False, float_format='%.15g')
    result.benchmark_trades.to_csv(output / 'benchmark_trades.csv', index=False, float_format='%.15g')
    result.benchmark_equity.to_csv(output / 'benchmark_equity.csv', index=False, float_format='%.15g')
    with (output / 'metrics.json').open('w') as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False, allow_nan=False)
    strategy, _ = resolve_strategy_config(report['audit']['strategy_config'])
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
    parser.add_argument('--observe-only',action='store_true',help='Chan-FX structure observation without execution or accounting')
    parser.add_argument('--dataset-id', help='Explicit frozen version (required when ambiguous)')
    args = parser.parse_args()
    with args.strategy_config.open() as handle:
        original_strategy = yaml.safe_load(handle)
    strategy, original_strategy = resolve_strategy_config(original_strategy)
    config = read_config(args.backtest_config, [
        'initial_cash', 'commission_rate', 'slippage_rate', 'start_date', 'end_date',
        'reports_dir', 'annualization_factor', 'risk_free_rate',
    ])
    store = DataStore.from_config(args.data_config, args.data_root)
    if strategy.get('name') == 'chan_fx':
        if not args.observe_only:
            raise NotImplementedError('Chan-FX trading rules and Forex execution are undefined; use --observe-only')
        if not args.dataset_id:
            raise ValueError('Chan observation requires an explicit dataset ID')
        if strategy['asset_class'] != 'forex' or strategy['price_basis'] != 'raw':
            raise ValueError('Chan-FX observer requires Forex raw bars')
        from quant_lab.chan import ChanConfig
        from quant_lab.strategies.chan_fx import ChanFxStrategy
        from quant_lab.strategies.base import StrategyContext
        from quant_lab.data.inspection import write_chan_outputs
        first,last = pd.Timestamp(config['start_date']),pd.Timestamp(config['end_date'])
        if first.tzinfo is None: first=first.tz_localize('UTC')
        if last.tzinfo is None: last=last.tz_localize('UTC')+pd.Timedelta(days=1)-pd.Timedelta(nanoseconds=1)
        data=load_dataset(args.dataset_id,store=store,symbols=[strategy['symbol']],
            timeframe=strategy['timeframe'],start=first,end=last)
        manifest=data.attrs['manifests'][0]
        instrument=next(x for x in manifest['instruments'] if x['symbol']==strategy['symbol'])
        if instrument['asset_class'] != 'forex':
            raise ValueError('Configured asset class does not match dataset')
        observer=ChanFxStrategy(ChanConfig(**strategy['chan']))
        for i,bar in enumerate(iter_bars(data)):
            observer.on_bar(StrategyContext(i,bar.available_at),bar)
        output=ROOT/config['reports_dir']/('chan_'+args.dataset_id)
        counts=write_chan_outputs(observer.analyzer,output,audit={'mode':'structure_observation_only',
            'strategy_config':original_strategy,'manifest':manifest,
            'assumptions':['No trades or Forex account are simulated; selected range is a cold start.']})
        print(json.dumps({'output':str(output),**counts},ensure_ascii=False))
        return
    if args.observe_only:
        raise ValueError('--observe-only is supported for chan_fx')
    if strategy.get('asset_class','equity') != 'equity':
        raise NotImplementedError('Forex/futures execution and accounting rules are undefined; use structure observation')
    selected = store.load_manifest(args.dataset_id) if args.dataset_id else None
    v3 = selected is not None and selected['schema_version'] == 3
    if v3:
        requested_tf = strategy.get('timeframe','1d')
        def utc_boundary(value, end=False):
            stamp = pd.Timestamp(value)
            if stamp.tzinfo is None:
                stamp = stamp.tz_localize('UTC')
                if end:
                    stamp += pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
            return stamp
        data = load_dataset(args.dataset_id,store=store,symbols=[strategy['symbol']],
            start=utc_boundary(config['start_date']),end=utc_boundary(config['end_date'],True),
            timeframe=requested_tf,price_basis=strategy['price_basis'])
        instrument = next(x for x in selected['instruments'] if x['symbol']==strategy['symbol'])
        if instrument['asset_class'] != strategy.get('asset_class','equity'):
            raise ValueError('Configured asset class does not match dataset')
        if strategy.get('venue') is not None and strategy['venue'] != instrument['venue']:
            raise ValueError('Configured venue does not match dataset')
        from quant_lab.backtest.engine import BacktestEngine
        from quant_lab.backtest.execution import EquityCashExecutionModel, EquityBuyAndHoldExecutionModel
        from quant_lab.backtest.portfolio import EquityPortfolio
        from quant_lab.backtest.models import BacktestResult
        from quant_lab.strategies.sma import SmaCrossStrategy
        from quant_lab.validation import strategy_future_mutation_test
        raw = tuple(iter_bars(data,requested_tf))
        if len(raw) <= strategy['slow_window']:
            raise ValueError('Require at least one eligible execution bar')
        cutoffs = sorted(set([strategy['slow_window']-1,len(raw)//2,len(raw)-2]))
        factory = lambda: SmaCrossStrategy(strategy['fast_window'],strategy['slow_window'])
        for cutoff in cutoffs:
            strategy_future_mutation_test(raw,raw[cutoff].available_at,factory)
        costs = Costs(config['commission_rate'],config['slippage_rate'])
        simulation = BacktestEngine(factory(),EquityCashExecutionModel(costs),EquityPortfolio(config['initial_cash'])).run(raw)
        benchmark = BacktestEngine(factory(),EquityBuyAndHoldExecutionModel(costs),EquityPortfolio(config['initial_cash'])).run(raw)
        result = BacktestResult(simulation.equity,simulation.trades,benchmark.equity,benchmark.trades)
        time_column = 'timestamp'
    else:
        if strategy.get('timeframe','1d') != '1d':
            raise ValueError('Intraday data requires an explicit V3 dataset ID')
        data = load_bars(strategy['market'],[strategy['symbol']],config['start_date'],config['end_date'],
            price_basis=strategy['price_basis'],store=store,dataset_id=args.dataset_id)
        if (data.date.iloc[0]-pd.Timestamp(config['start_date'])).days>7 or (pd.Timestamp(config['end_date'])-data.date.iloc[-1]).days>7:
            raise ValueError('Dataset does not cover requested experiment range')
        if len(data)<=strategy['slow_window']:
            raise ValueError('Require at least one eligible execution session')
        cutoffs = sorted(set([strategy['slow_window']-1,len(data)//2,len(data)-2]))
        for cutoff in cutoffs:
            future_mutation_test(data,data.date.iloc[cutoff],strategy['fast_window'],strategy['slow_window'])
        result = run_backtest(data,strategy['fast_window'],strategy['slow_window'],config['initial_cash'],
            Costs(config['commission_rate'],config['slippage_rate']),strategy['symbol'])
        time_column = 'date'
    manifests = data.attrs['manifests']
    manifest = manifests[0]
    checksum = manifest['normalized_sha256']
    for item in manifests:
        if item['schema_version'] in (2,3):
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
        'Metrics include warmup cash; risk and drawdown use last known valuation per UTC calendar day, CAGR uses calendar years.',
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
    currency = (instrument.get('quote_currency') or 'unspecified') if v3 else ('CNY' if strategy['market']=='CN' else 'USD')
    report = {
        'strategy': calculate_metrics(result.equity, result.trades, config['initial_cash'],
                                      config['annualization_factor'], config['risk_free_rate']),
        'benchmark': calculate_metrics(result.benchmark_equity, result.benchmark_trades, config['initial_cash'],
                                       config['annualization_factor'], config['risk_free_rate']),
        'audit': {
            'strategy_config': original_strategy, 'backtest_config': config, 'data_sha256': checksum,
            'data_provenance': manifest, 'manifest': manifest,
            'market': manifest.get('market'), 'asset_class': strategy.get('asset_class','equity'),
            'timeframe': strategy.get('timeframe','1d'), 'provider': manifest['provider'],
            'price_basis': strategy['price_basis'], 'dataset_id': manifest['dataset_id'], 'currency': currency,
            'data_storage': {'root': str(store.root), **store.storage},
            'manifest_sha256': file_sha256(store.manifest_path(manifest['dataset_id'])) if manifest['schema_version'] in (2,3) else manifest['metadata_file']['sha256'],
            'actual_start': str(data[time_column].iloc[0]),
            'actual_end': str(data[time_column].iloc[-1]), 'rows': len(data),
            'metrics_frequency': 'daily', 'metrics_timezone': 'UTC',
            'future_mutation_test_passed': True,
            'future_mutation_cutoffs': [str(data[time_column].iloc[i]) for i in cutoffs],
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
