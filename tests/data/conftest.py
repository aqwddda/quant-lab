import pytest
from src.data.store import DataStore
from src.market import Instrument


@pytest.fixture
def canonical(bars):
    return bars.copy()


@pytest.fixture
def store(tmp_path):
    return DataStore(tmp_path)


@pytest.fixture
def dataset_options():
    return dict(provider='fixture', provider_version='1', instruments=[
        Instrument('AAPL','AAPL','equity','NASDAQ',quote_currency='USD')],
        timeframe='1d', source_timezone='UTC')


@pytest.fixture
def saved(store, canonical, dataset_options):
    return store.save_dataset(canonical, dataset_id='fixture_AAPL',
        source_frames={'bars':canonical}, **dataset_options)
