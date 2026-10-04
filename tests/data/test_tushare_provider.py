import pandas as pd
import pytest
from src.data.providers.tushare import TushareProvider
from src.data.normalize import normalize_tushare


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
    manifest = store.save_dataset(**normalized, dataset_id=f'tushare_CN_{symbol}_v1', provider='tushare',
        provider_version=snapshot.provider_version, market='CN', asset_type='EQUITY', start='2020-01-02',
        end='2020-01-03', source_frames=snapshot.source_frames, assumptions=snapshot.assumptions)
    assert store.verify(manifest)['bars'].symbol.eq(symbol).all()


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
