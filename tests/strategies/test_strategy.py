import pandas as pd
import pytest
from src.data.loader import iter_bars
from src.strategies.sma import SmaCrossStrategy
from src.strategies.base import StrategyContext


def decisions(data, fast=20, slow=60):
    strategy=SmaCrossStrategy(fast,slow)
    return [strategy.on_bar(StrategyContext(i,bar.available_at),bar)
        for i,bar in enumerate(iter_bars(data,'1d'))]


def test_moving_averages_and_warmup(bars):
    result=decisions(bars)
    assert result[19].diagnostics['fast_ma']==109.5
    assert result[59].diagnostics['slow_ma']==129.5
    assert all(x.target is None for x in result[:59])
    assert result[59].target==1


def test_equality_is_cash(bars):
    bars['close']=100.;bars['open']=100.;bars['high']=101.;bars['low']=99.
    assert decisions(bars)[59].target==0


@pytest.mark.parametrize('fast,slow',[(0,60),(60,20),(20.5,60),(True,60)])
def test_invalid_windows(fast,slow):
    with pytest.raises(ValueError): SmaCrossStrategy(fast,slow)
