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
from src.data_loader import file_sha256, load_market_data
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
    for filename, column, ylabel, multiplier in [
        ('equity_curve.png', 'equity', 'Equity (USD)', 1),
        ('drawdown.png', 'drawdown', 'Drawdown (%)', 100),
    ]:
        fig, ax = plt.subplots(figsize=(11, 5), layout='constrained')
        ax.plot(result.equity.date, result.equity[column] * multiplier, label='SPY SMA 20/60')
        ax.plot(result.benchmark_equity.date, result.benchmark_equity[column] * multiplier,
                label='SPY buy & hold', alpha=0.8)
        ax.set(xlabel='New York session date', ylabel=ylabel,
               title='Net of commission and slippage; adjusted OHLC')
        ax.legend()
        ax.grid(alpha=0.25)
        fig.savefig(output / filename, dpi=150)
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strategy-config', type=Path, default=ROOT / 'config/strategy.yaml')
    parser.add_argument('--backtest-config', type=Path, default=ROOT / 'config/backtest.yaml')
    args = parser.parse_args()
    strategy = read_config(args.strategy_config, ['symbol', 'fast_window', 'slow_window'])
    config = read_config(args.backtest_config, [
        'initial_cash', 'commission_rate', 'slippage_rate', 'start_date', 'end_date',
        'data_path', 'reports_dir', 'annualization_factor', 'risk_free_rate',
    ])
    path = ROOT / config['data_path']
    metadata_path = path.with_suffix('.metadata.json')
    with metadata_path.open() as handle:
        provenance = json.load(handle)
    checksum = file_sha256(path)
    if provenance['sha256'] != checksum or provenance['symbol'] != strategy['symbol'] or provenance['auto_adjust'] is not True:
        raise ValueError('Frozen data provenance/checksum/adjustment mismatch')
    data = load_market_data(path, config['start_date'], config['end_date'])
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
    if file_sha256(path) != checksum:
        raise ValueError('Data file changed during the run')
    report = {
        'strategy': calculate_metrics(result.equity, result.trades, config['initial_cash'],
                                      config['annualization_factor'], config['risk_free_rate']),
        'benchmark': calculate_metrics(result.benchmark_equity, result.benchmark_trades, config['initial_cash'],
                                       config['annualization_factor'], config['risk_free_rate']),
        'audit': {
            'strategy_config': strategy, 'backtest_config': config, 'data_sha256': checksum,
            'data_provenance': provenance, 'actual_start': str(data.date.iloc[0].date()),
            'actual_end': str(data.date.iloc[-1].date()), 'rows': len(data),
            'future_mutation_test_passed': True,
            'future_mutation_cutoffs': [str(data.date.iloc[i].date()) for i in cutoffs],
            'python_version': platform.python_version(),
            'package_versions': {name: version(name) for name in ['pandas', 'numpy', 'pyarrow', 'PyYAML', 'matplotlib', 'yfinance']},
            'source_sha256': {str(p.relative_to(ROOT)): file_sha256(p)
                              for directory in ['src', 'scripts'] for p in sorted((ROOT / directory).glob('*.py'))},
            'assumptions': [
                'Signal at T close; fill at next available session open, never at T close.',
                'Adjusted OHLC represents a synthetic dividend/split-adjusted price series; no separate dividend cash flows.',
                'Integer synthetic adjusted shares, all cash allocation, no interest, borrowing, taxes or minimum fees.',
                'Slippage is embedded in execution_price and never deducted twice.',
                'No end-date liquidation; final holdings marked at adjusted close.',
                'Benchmark buys once at first eligible open (session 61) with identical costs and initial cash.',
                'Metrics include warmup cash sessions; CAGR uses calendar years, volatility/Sharpe use configured sessions/year.',
                'Trade count counts fills; win rate, profit factor and holding days use closed round trips only.',
                'Sortino uses RMS negative excess returns over all sessions; turnover is gross traded value / mean equity, not annualized.',
                'Undefined ratios are JSON null, including profit factor when there are no losses.',
                'Data checks reject invalid bars but do not independently verify every exchange holiday or missing session.',
            ],
        },
    }
    write_reports(result, report, ROOT / config['reports_dir'])
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
