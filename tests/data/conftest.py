import pandas as pd
import pytest
from src.data.store import DataStore


@pytest.fixture
def canonical(bars):
    data = bars.copy()
    data['date'] = data.date.astype('datetime64[ns]')
    data.insert(1, 'symbol', 'AAPL')
    return data


@pytest.fixture
def store(tmp_path):
    return DataStore(tmp_path)


@pytest.fixture
def saved(store, canonical):
    return store.save_dataset(canonical, dataset_id='fixture_US_AAPL_v1', provider='fixture',
                              provider_version='1', market='US', asset_type='EQUITY',
                              start='2020-01-01', end=str(canonical.date.iloc[-1].date()),
                              source_frames={'bars': canonical})
