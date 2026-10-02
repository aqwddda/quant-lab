import numpy as np
import pandas as pd
import pytest
from src.data_loader import load_market_data
from src.validation import validate_market_data


@pytest.mark.parametrize('problem', ['duplicate', 'unsorted', 'missing', 'zero', 'high', 'low',
                                    'timezone', 'time', 'volume', 'infinite', 'weekend'])
def test_reject_bad_data(bars, problem):
    data = bars.copy()
    if problem == 'duplicate':
        data.loc[1, 'date'] = data.loc[0, 'date']
    elif problem == 'unsorted':
        data = data.iloc[::-1]
    elif problem == 'missing':
        data.loc[0, 'close'] = np.nan
    elif problem == 'zero':
        data.loc[0, 'open'] = 0
    elif problem == 'high':
        data.loc[0, 'high'] = 99
    elif problem == 'low':
        data.loc[0, 'low'] = 101
    elif problem == 'timezone':
        data['date'] = data.date.dt.tz_localize('UTC')
    elif problem == 'time':
        data['date'] += pd.Timedelta(hours=1)
    elif problem == 'volume':
        data.loc[0, 'volume'] = -1
    elif problem == 'infinite':
        data.loc[0, 'close'] = np.inf
    elif problem == 'weekend':
        data.loc[0, 'date'] = pd.Timestamp('2019-12-29')
    with pytest.raises(ValueError):
        validate_market_data(data)


def test_parquet_loader_and_no_silent_repair(bars, tmp_path):
    path = tmp_path / 'bars.parquet'
    bars.to_parquet(path, index=False)
    result = load_market_data(path, bars.date.iloc[5], bars.date.iloc[10])
    pd.testing.assert_frame_equal(result, bars.iloc[5:11].reset_index(drop=True))
    bars.iloc[::-1].to_parquet(path, index=False)
    with pytest.raises(ValueError):
        load_market_data(path, bars.date.iloc[0], bars.date.iloc[-1])


def test_missing_dataset_does_not_download(tmp_path):
    with pytest.raises(FileNotFoundError, match='separately'):
        load_market_data(tmp_path / 'missing.parquet', '2015-01-01', '2025-12-31')
