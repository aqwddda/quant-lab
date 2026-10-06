"""Yahoo transport and exchange timezone conversion, without storage or trading."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
from src.data.models import ProviderSnapshot
from src.data.providers.base import check_request


def session_labels(index, exchange_timezone):
    dates = pd.DatetimeIndex(index)
    if dates.tz is None:
        raise ValueError('Provider timestamps lack exchange timezone')
    return dates.tz_convert(exchange_timezone).tz_localize(None).normalize().astype('datetime64[ns]')


class YahooProvider:
    name = 'yahoo'
    market = 'US'

    def __init__(self, cache_dir=None, client=None):
        if client is None:
            import yfinance
            client = yfinance
        self.client = client
        self.version = str(getattr(client, '__version__', 'injected-client'))
        if cache_dir is not None:
            self.client.set_tz_cache_location(str(Path(cache_dir)))
        self.source_frames = {}
        self._request = None

    def fetch_bars(self, symbol, start, end, frequency='1d'):
        _, last = check_request(symbol, start, end, frequency)
        self.ticker = self.client.Ticker(symbol)
        history = self.ticker.history(start=start, end=(last + timedelta(days=1)).isoformat(),
                                      interval='1d', auto_adjust=False, back_adjust=False,
                                      repair=False, actions=True, keepna=True, raise_errors=True)
        if history.empty:
            raise ValueError('Provider returned no data')
        self.source_frames = {'bars': history.copy(deep=True)}
        self.exchange_timezone = self.ticker.get_history_metadata()['exchangeTimezoneName']
        data = history.reset_index(drop=True)
        data.insert(0, 'date', session_labels(history.index, self.exchange_timezone))
        if not data.date.between(pd.Timestamp(start), pd.Timestamp(end)).all():
            raise ValueError('Provider returned out-of-range dates')
        self._request = (symbol, start, end)
        self.bars = data
        return data.copy(deep=True)

    def _ensure_bars(self, symbol, start, end):
        if self._request != (symbol, start, end):
            self.fetch_bars(symbol, start, end)

    def fetch_adjustments(self, symbol, start, end):
        self._ensure_bars(symbol, start, end)
        # Yahoo OHLC with auto_adjust=False is already split adjusted. All known
        # splits, including those AFTER requested end, are needed to undo that.
        history = self.ticker.history(period='max', interval='1d', auto_adjust=False,
                                      back_adjust=False, repair=False, actions=True,
                                      keepna=True, raise_errors=True)
        if history.empty or 'Stock Splits' not in history or history['Stock Splits'].isna().any():
            raise ValueError('Invalid Yahoo split history')
        self.source_frames['adjustments'] = history.copy(deep=True)
        events = history.loc[history['Stock Splits'] != 0, 'Stock Splits']
        dates = session_labels(events.index, self.exchange_timezone)
        return pd.DataFrame({'date': dates, 'Stock Splits': events.to_numpy(dtype=float)})

    def fetch_corporate_actions(self, symbol, start, end):
        self._ensure_bars(symbol, start, end)
        columns = ['date', 'Dividends', 'Stock Splits']
        if not set(columns).issubset(self.bars):
            raise ValueError('Yahoo action columns missing')
        return self.bars[columns].copy()

    def fetch_instrument(self, symbol):
        if self._request is None or self._request[0] != symbol:
            raise ValueError('Fetch bars before instrument reference')
        info = self.ticker.get_info()
        if info.get('symbol') != symbol:
            raise ValueError('Yahoo instrument symbol mismatch')
        self.source_frames['instruments'] = info.copy()
        return info.copy()

    def fetch_calendar(self, start, end):
        raise NotImplementedError('Yahoo has no independently verified exchange calendar here')

    def fetch_snapshot(self, symbol, start, end, frequency='1d'):
        prepared = {'bars': self.fetch_bars(symbol, start, end, frequency),
                    'adjustments': self.fetch_adjustments(symbol, start, end),
                    'corporate_actions': self.fetch_corporate_actions(symbol, start, end),
                    'instruments': self.fetch_instrument(symbol)}
        prepared['source_timezone'] = self.exchange_timezone
        return ProviderSnapshot(self.source_frames.copy(), prepared, self.version, [
            'Exact exchange holiday completeness is not independently verified.',
            'Yahoo auto_adjust=False OHLC is split adjusted; raw OHLC is reconstructed using all frozen known subsequent splits.',
            'Yahoo provider_adjusted OHLC uses Adj Close / reconstructed raw Close; volume is not price adjusted by the loader.',
            'Yahoo source volume and dividend amounts are de-scaled by subsequent splits during explicit normalization.',
            'No repair, fill, or deduplication; supplier revisions and missing corporate actions cannot be ruled out.',
            'This is a download-time snapshot, not independently verified point-in-time data.',
        ])



from src.data.providers.base import ProviderCapabilities
from src.market import AssetClass, Timeframe
YahooProvider.capabilities = ProviderCapabilities(frozenset({AssetClass.EQUITY}),
    frozenset({Timeframe.D1}), supports_adjustments=True, supports_corporate_actions=True)
