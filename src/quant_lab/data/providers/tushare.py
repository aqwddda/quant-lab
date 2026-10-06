"""Tushare raw daily transport. Token is read from an environment variable only."""
import os
import re
import pandas as pd
from quant_lab.data.models import ProviderSnapshot
from quant_lab.data.providers.base import check_request


class TushareProvider:
    name = 'tushare'
    market = 'CN'

    def __init__(self, token_env='TUSHARE_TOKEN', client=None):
        token = os.environ.get(token_env, '').strip()
        if not token:
            raise ValueError(f'{token_env} is not configured')
        if client is None:
            import tushare
            client = tushare
        self.client = client
        self.api = client.pro_api(token)
        self.version = str(getattr(client, '__version__', 'injected-client'))
        self.source_frames = {}
        self.exchange = 'SSE'

    def _parameters(self, symbol, start, end, frequency='1d'):
        check_request(symbol, start, end, frequency)
        if not re.fullmatch(r'\d{6}\.(SZ|SH|BJ)', symbol):
            raise ValueError('Tushare requires canonical A-share symbol, e.g. 000001.SZ')
        self.exchange = {'SH': 'SSE', 'SZ': 'SZSE', 'BJ': 'BSE'}[symbol[-2:]]
        return {'ts_code': symbol, 'start_date': start.replace('-', ''), 'end_date': end.replace('-', '')}

    def _capture(self, name, data):
        if not isinstance(data, pd.DataFrame) or data.empty:
            raise ValueError(f'Tushare returned no {name} data')
        # Do not present an API limit as a complete historical dataset.
        if len(data) >= 6000:
            raise ValueError('Tushare response may be truncated at 6000 rows; request a shorter interval')
        self.source_frames[name] = data.copy(deep=True)
        return data.copy(deep=True)

    def fetch_bars(self, symbol, start, end, frequency='1d'):
        self.source_frames = {}
        params = self._parameters(symbol, start, end, frequency)
        return self._capture('bars', self.api.daily(**params))

    def fetch_adjustments(self, symbol, start, end):
        return self._capture('adjustments', self.api.adj_factor(**self._parameters(symbol, start, end)))

    def fetch_instrument(self, symbol):
        for status in ['L', 'D', 'P']:
            data = self.api.stock_basic(ts_code=symbol, list_status=status,
                                        fields='ts_code,name,exchange,list_date,delist_date')
            if isinstance(data, pd.DataFrame) and not data.empty:
                return self._capture('instruments', data)
        raise ValueError('Tushare returned no instrument data')

    def fetch_calendar(self, start, end):
        check_request('calendar', start, end)
        return self._capture('calendar', self.api.trade_cal(exchange=self.exchange,
            start_date=start.replace('-', ''), end_date=end.replace('-', ''),
            fields='exchange,cal_date,is_open'))

    def fetch_corporate_actions(self, symbol, start, end):
        raise NotImplementedError('Tushare corporate action event normalization is not implemented')

    def fetch_snapshot(self, symbol, start, end, frequency='1d'):
        prepared = {'bars': self.fetch_bars(symbol, start, end, frequency),
                    'adjustments': self.fetch_adjustments(symbol, start, end),
                    'instruments': self.fetch_instrument(symbol), 'calendar': self.fetch_calendar(start, end)}
        return ProviderSnapshot(self.source_frames.copy(), prepared, self.version, [
            'Tushare daily prices are unadjusted; source vol is in lots of 100 shares and amount in thousands of CNY.',
            'Normalization converts volume to shares and amount to CNY, with explicit ascending date order.',
            'Adjustment factors are cumulative provider-scaled factors; no missing-factor filling.',
            'Calendar comes from the instrument exchange; suspended sessions may have no bars.',
            'Tushare corporate action event normalization is unsupported; factors do not replace event records.',
            'Instrument reference is the download-time snapshot, not historical point-in-time reference data.',
        ])
