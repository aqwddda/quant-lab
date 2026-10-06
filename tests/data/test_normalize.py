import pandas as pd
import pytest
from src.data.normalization.yahoo import normalize_yahoo
from src.data.normalization import integer_volume
from src.data.providers.yahoo import YahooProvider
from tests.data.test_yahoo_provider import FakeYahoo


def test_sort_is_only_an_explicit_normalization_step():
    snapshot = YahooProvider(client=FakeYahoo()).fetch_snapshot('AAPL', '2020-08-28', '2020-08-31')
    snapshot.prepared['bars'] = snapshot.prepared['bars'].iloc[::-1]
    result = normalize_yahoo(snapshot.prepared, 'AAPL')
    assert result['bars'].date.is_monotonic_increasing


def test_splits_after_request_end_are_used_to_reconstruct_raw():
    snapshot = YahooProvider(client=FakeYahoo()).fetch_snapshot('AAPL', '2020-08-28', '2020-08-31')
    snapshot.prepared['adjustments'] = pd.concat([snapshot.prepared['adjustments'],
        pd.DataFrame({'date': pd.to_datetime(['2022-01-03']).astype('datetime64[ns]'), 'Stock Splits': [3.]})])
    # A later 3:1 split also triples Yahoo's historical split-adjusted volume.
    snapshot.prepared['bars']['Volume'] *= 3
    result = normalize_yahoo(snapshot.prepared, 'AAPL')
    assert result['bars'].close.tolist() == [300., 150.]
    # Source volumes must be divisible into integral historical shares.


@pytest.mark.parametrize('value', [1000.5, -1, float('nan'), float('inf')])
def test_volume_conversion_does_not_round_bad_values(value):
    with pytest.raises(ValueError):
        integer_volume(pd.Series([value]))


@pytest.mark.parametrize('exchange,currency', [('HKG', 'HKD'), ('LSE', 'USD')])
def test_foreign_instrument_cannot_be_mislabeled_us(exchange, currency):
    snapshot = YahooProvider(client=FakeYahoo()).fetch_snapshot('AAPL', '2020-08-28', '2020-08-31')
    snapshot.prepared['instruments'].update({'exchange': exchange, 'currency': currency})
    with pytest.raises(ValueError, match='US exchange'):
        normalize_yahoo(snapshot.prepared, 'AAPL')
