import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def bars():
    close = np.arange(100.0, 220.0)
    dates = pd.bdate_range('2020-01-01', periods=len(close)).astype('datetime64[ns]')
    return pd.DataFrame({
        'timestamp': dates.tz_localize('UTC'), 'date': dates, 'symbol': 'AAPL',
        'open': close, 'high': close + 1, 'low': close - 1,
        'close': close, 'volume': np.full(len(close), 1000),
    })
