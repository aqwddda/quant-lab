from pathlib import Path
import pytest
from src.data.loader import load_bars
from src.data.manifest import file_sha256
from src.backtest import run_backtest
from src.execution import Costs
from src.metrics import calculate_metrics
from src.validation import future_mutation_test

ROOT = Path(__file__).resolve().parents[1]
SPY_HASH = 'bdd34d3bc950d433a5eeeaa594be558dd1c920dacbd61f8750366d8836bca19f'


def test_legacy_spy_regression():
    path = ROOT / 'data/raw/spy_daily.parquet'
    if not path.is_file():
        pytest.skip('Frozen V1 SPY experiment is not distributed in Git; supply its audited dataset')
    assert file_sha256(path) == SPY_HASH
    data = load_bars('US', ['SPY'], '2015-01-01', '2025-12-31', price_basis='legacy_provider_adjusted')
    assert len(data) == 2766
    assert str(data.date.iloc[0].date()) == '2015-01-02'
    assert str(data.date.iloc[-1].date()) == '2025-12-31'
    future_mutation_test(data, data.date.iloc[59], 20, 60)
    result = run_backtest(data, 20, 60, 100000, Costs(0.0005, 0.0002), 'SPY')
    metrics = calculate_metrics(result.equity, result.trades, 100000, 252, 0)
    benchmark = calculate_metrics(result.benchmark_equity, result.benchmark_trades, 100000, 252, 0)
    assert len(result.trades) == 45
    assert len(result.benchmark_trades) == 1
    assert metrics['total_return'] == pytest.approx(1.466718879583301, rel=1e-13)
    assert metrics['cagr'] == pytest.approx(0.08558235360852229, rel=1e-13)
    assert benchmark['total_return'] == pytest.approx(2.9389675730204616, rel=1e-13)
    assert benchmark['cagr'] == pytest.approx(0.13278961489741126, rel=1e-13)
    for account in [result.equity, result.benchmark_equity]:
        assert (account.equity == account.cash + account.position_market_value).all()
        assert (account.equity - 100000).to_numpy() == pytest.approx((account.realized_pnl + account.unrealized_pnl).to_numpy())
    assert file_sha256(path) == SPY_HASH
