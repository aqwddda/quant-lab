import pandas as pd
import pytest
from src.data.providers.yahoo import YahooProvider, session_labels
from src.data.normalize import normalize_yahoo


class FakeYahoo:
    __version__ = 'fixture-1'

    def __init__(self):
        self.calls = []

    def Ticker(self, symbol):
        client = self

        class Ticker:
            def history(self, **kwargs):
                client.calls.append(kwargs)
                # UTC timestamps near midnight must retain the local session date.
                return pd.DataFrame({'Open': [50., 50.], 'High': [51., 51.], 'Low': [49., 49.],
                    'Close': [50., 50.], 'Adj Close': [49., 49.], 'Volume': [2000, 1000],
                    'Dividends': [0., 0.5], 'Stock Splits': [0., 2.]},
                    index=pd.DatetimeIndex(['2020-08-29 00:00Z', '2020-09-01 00:00Z'], name='Date'))

            def get_history_metadata(self):
                return {'exchangeTimezoneName': 'America/New_York'}

            def get_info(self):
                return {'symbol': symbol, 'quoteType': 'EQUITY', 'exchange': 'NMS',
                        'currency': 'USD', 'longName': 'Apple Inc.'}

        return Ticker()


def test_inclusive_end_timezone_and_frozen_source():
    client = FakeYahoo()
    provider = YahooProvider(client=client)
    snapshot = provider.fetch_snapshot('AAPL', '2020-08-28', '2020-08-31')
    call = client.calls[0]
    assert call['end'] == '2020-09-01'
    assert call['auto_adjust'] is False and call['repair'] is False and call['actions'] is True
    assert client.calls[1]['period'] == 'max'
    assert client.calls[1]['repair'] is False and client.calls[1]['auto_adjust'] is False
    assert snapshot.source_frames['bars'].index.tz is not None
    assert snapshot.prepared['bars'].date.tolist() == [pd.Timestamp('2020-08-28'), pd.Timestamp('2020-08-31')]
    normalized = normalize_yahoo(snapshot.prepared, 'AAPL')
    assert normalized['bars'].close.tolist() == [100., 50.]
    assert normalized['bars'].volume.tolist() == [1000, 1000]
    assert normalized['adjustments'].adj_factor.tolist() == [0.49, 0.98]
    assert set(normalized['corporate_actions'].action_type) == {'dividend', 'split'}


def test_timezone_is_required():
    with pytest.raises(ValueError, match='timezone'):
        session_labels(pd.date_range('2020-01-01', periods=2), 'America/New_York')


def test_unsupported_calendar_is_explicit():
    with pytest.raises(NotImplementedError):
        YahooProvider(client=FakeYahoo()).fetch_calendar('2020-01-01', '2020-01-10')
