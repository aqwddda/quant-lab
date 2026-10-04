import numpy as np
import pandas as pd
import pytest
from src.data.validation import validate_daily_bars


@pytest.mark.parametrize('problem', ['duplicate', 'unsorted', 'nan', 'inf', 'zero', 'negative',
                                    'high', 'low', 'negative_volume', 'fractional_volume',
                                    'timezone', 'time', 'weekend', 'numeric_string'])
def test_reject_without_repair(canonical, problem):
    data = canonical.copy()
    if problem == 'duplicate':
        data.loc[1, 'date'] = data.date.iloc[0]
    elif problem == 'unsorted':
        data = data.iloc[::-1]
    elif problem == 'timezone':
        data['date'] = data.date.dt.tz_localize('UTC')
    elif problem == 'time':
        data['date'] += pd.Timedelta(hours=1)
    elif problem == 'weekend':
        data.loc[0, 'date'] = pd.Timestamp('2019-12-29')
    elif problem == 'numeric_string':
        data['close'] = data.close.astype(str)
    else:
        column, value = {'nan': ('close', np.nan), 'inf': ('close', np.inf),
                         'zero': ('open', 0), 'negative': ('open', -1), 'high': ('high', 1),
                         'low': ('low', 10000), 'negative_volume': ('volume', -1),
                         'fractional_volume': ('volume', 1000.5)}[problem]
        data[column] = data[column].astype(float)
        data.loc[0, column] = value
    before = data.copy(deep=True)
    with pytest.raises(ValueError):
        validate_daily_bars(data, 'US')
    pd.testing.assert_frame_equal(data, before)


def test_cn_calendar_requires_known_open_session(canonical):
    calendar = pd.DataFrame({'date': canonical.date, 'market': 'CN', 'is_open': True, 'provider': 'fixture'})
    validate_daily_bars(canonical, 'CN', calendar)
    calendar.loc[0, 'is_open'] = False
    with pytest.raises(ValueError, match='not marked open'):
        validate_daily_bars(canonical, 'CN', calendar)
