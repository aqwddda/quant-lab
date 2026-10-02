import pytest
from src.strategy import calculate_signals


def test_moving_averages_and_warmup(bars):
    result = calculate_signals(bars, 20, 60)
    assert result.fast_ma.iloc[19] == 109.5
    assert result.slow_ma.iloc[59] == 129.5
    assert (result.target.iloc[:59] == -1).all()
    assert result.target.iloc[59] == 1


def test_equality_is_cash(bars):
    bars['close'] = 100.0
    result = calculate_signals(bars, 20, 60)
    assert result.target.iloc[59] == 0


@pytest.mark.parametrize('fast,slow', [(0, 60), (60, 20), (20.5, 60), (True, 60)])
def test_invalid_windows(bars, fast, slow):
    with pytest.raises(ValueError):
        calculate_signals(bars, fast, slow)
