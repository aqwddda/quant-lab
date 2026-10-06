import pandas as pd
import pytest
from src.data.providers.tushare import TushareProvider
from src.data.normalization.tushare import normalize_tushare
from src.market import Instrument, AssetClass


class FakeTushare:
    __version__ = 'fixture-1'

    def __init__(self, symbol='000001.SZ'):
        self.symbol = symbol
        self.calls = []

    def pro_api(self, token):
        assert token == 'fixture-token'
        return self

    def daily(self, **kwargs):
        self.calls.append(('daily', kwargs))
        return pd.DataFrame({'ts_code': [self.symbol] * 2, 'trade_date': ['20200103', '20200102'],
            'open': [50., 100.], 'high': [51., 101.], 'low': [49., 99.], 'close': [50., 100.],
            'pre_close': [50., 100.], 'vol': [10.25, 20.5], 'amount': [5.125, 20.5]})

    def adj_factor(self, **kwargs):
        self.calls.append(('adj_factor', kwargs))
        return pd.DataFrame({'ts_code': [self.symbol] * 2, 'trade_date': ['20200103', '20200102'],
                             'adj_factor': [4., 2.]})

    def stock_basic(self, **kwargs):
        return pd.DataFrame({'ts_code': [self.symbol], 'name': ['fixture'],
                             'exchange': ['SZSE' if self.symbol.endswith('SZ') else 'SSE'],
                             'list_date': ['19910403'], 'delist_date': [None]})

    def trade_cal(self, **kwargs):
        self.calls.append(('trade_cal', kwargs))
        return pd.DataFrame({'exchange': [kwargs['exchange']] * 2,
                             'cal_date': ['20200103', '20200102'], 'is_open': [1, 1]})


def test_missing_token_fails(monkeypatch):
    monkeypatch.delenv('TUSHARE_TOKEN', raising=False)
    with pytest.raises(ValueError, match='TUSHARE_TOKEN is not configured'):
        TushareProvider(client=FakeTushare())


@pytest.mark.parametrize('symbol', ['000001.SZ', '600519.SH'])
def test_source_normalization_units_calendar_and_store(monkeypatch, store, symbol):
    monkeypatch.setenv('TUSHARE_TOKEN', 'fixture-token')
    client = FakeTushare(symbol)
    snapshot = TushareProvider(client=client).fetch_snapshot(symbol, '2020-01-02', '2020-01-03')
    assert client.calls[0] == ('daily', {'ts_code': symbol, 'start_date': '20200102', 'end_date': '20200103'})
    assert snapshot.source_frames['bars'].trade_date.tolist() == ['20200103', '20200102']
    normalized = normalize_tushare(snapshot.prepared, symbol)
    assert normalized['bars'].date.dt.strftime('%Y%m%d').tolist() == ['20200102', '20200103']
    assert normalized['bars'].volume.tolist() == [2050, 1025]
    assert normalized['bars'].amount.tolist() == [20500., 5125.]
    assert normalized['instruments'] == [Instrument(symbol, symbol, AssetClass.EQUITY,
        'SZSE' if symbol.endswith('.SZ') else 'SSE', quote_currency='CNY')]
    manifest = store.save_dataset(normalized['bars'], dataset_id=f'tushare_{symbol}_snapshot',
        provider='tushare',provider_version=snapshot.provider_version,source_timezone='Asia/Shanghai',
        session_timezone='Asia/Shanghai',timeframe='1d',instruments=normalized['instruments'],
        normalized_frames={k:v for k,v in normalized.items() if k not in {'bars', 'instruments'}},
        source_frames=snapshot.source_frames,assumptions=snapshot.assumptions)
    assert store.verify(manifest)['bars'].symbol.eq(symbol).all()


@pytest.mark.parametrize('symbol,code,venue', [('000001.SZ', 'SZSE', 'SZSE'),
    ('600519.SH', 'SSE', 'SSE'), ('430047.BJ', 'BSE', 'BSE')])
def test_supplier_exchange_maps_to_canonical_venue(monkeypatch, symbol, code, venue):
    monkeypatch.setenv('TUSHARE_TOKEN', 'fixture-token')
    snapshot = TushareProvider(client=FakeTushare(symbol)).fetch_snapshot(symbol, '2020-01-02', '2020-01-03')
    snapshot.prepared['instruments']['exchange'] = code
    assert normalize_tushare(snapshot.prepared, symbol)['instruments'] == [
        Instrument(symbol, symbol, 'equity', venue, quote_currency='CNY')]


def test_unknown_exchange_is_rejected(monkeypatch):
    monkeypatch.setenv('TUSHARE_TOKEN', 'fixture-token')
    snapshot = TushareProvider(client=FakeTushare()).fetch_snapshot('000001.SZ', '2020-01-02', '2020-01-03')
    snapshot.prepared['instruments']['exchange'] = 'UNKNOWN'
    with pytest.raises(ValueError, match='Unsupported Tushare exchange'):
        normalize_tushare(snapshot.prepared, '000001.SZ')


def test_unsupported_actions_are_explicit(monkeypatch):
    monkeypatch.setenv('TUSHARE_TOKEN', 'fixture-token')
    with pytest.raises(NotImplementedError):
        TushareProvider(client=FakeTushare()).fetch_corporate_actions('000001.SZ', '2020-01-02', '2020-01-03')


def test_missing_factor_fails_without_backfill(monkeypatch):
    monkeypatch.setenv('TUSHARE_TOKEN', 'fixture-token')
    snapshot = TushareProvider(client=FakeTushare()).fetch_snapshot('000001.SZ', '2020-01-02', '2020-01-03')
    snapshot.prepared['adjustments'] = snapshot.prepared['adjustments'].iloc[:1]
    with pytest.raises(ValueError, match='Missing adjustment factor'):
        normalize_tushare(snapshot.prepared, '000001.SZ')
