import pandas as pd
import pytest
import tushare
from src.data.adjustment import adjust_bars
from src.data.providers.tushare import TushareProvider
from src.data.normalization.tushare import normalize_tushare
from src.data.loader import load_dataset
from tests.data.test_tushare_provider import FakeTushare


def test_qfq_end_factor_on_session_without_bar(monkeypatch, store):
    monkeypatch.setenv('TUSHARE_TOKEN', 'fixture-token')
    class SuspendedAPI(FakeTushare):
        def adj_factor(self, **kwargs):
            return pd.concat([pd.DataFrame({'ts_code': ['000001.SZ'], 'trade_date': ['20200106'],
                                           'adj_factor': [8.]}), super().adj_factor(**kwargs)], ignore_index=True)
    api = SuspendedAPI()
    snapshot = TushareProvider(client=api).fetch_snapshot('000001.SZ', '2020-01-02', '2020-01-06')
    frames = normalize_tushare(snapshot.prepared, '000001.SZ')
    assert len(frames['adjustments']) == 3 and len(frames['bars']) == 2
    store.save_dataset(frames['bars'],dataset_id='suspended_factor',provider='tushare',provider_version='fixture',
        instruments=frames['instruments'],timeframe='1d',source_timezone='Asia/Shanghai',
        session_timezone='Asia/Shanghai',normalized_frames={k:v for k,v in frames.items() if k not in {'bars', 'instruments'}},
        source_frames=snapshot.source_frames)
    loaded=load_dataset('suspended_factor',end='2020-01-06T23:59:59+08:00',price_basis='qfq',store=store)
    assert loaded.close.tolist() == [25., 25.]
    expected = tushare.pro_bar(ts_code='000001.SZ', api=api, start_date='20200102', end_date='20200106',
                              adj='qfq', retry_count=1)
    assert loaded.close.to_numpy() == pytest.approx(expected.sort_values('trade_date').close.to_numpy())
    earlier = adjust_bars(frames['bars'], frames['adjustments'], 'qfq', anchor_end='2020-01-03')
    assert earlier.close.tolist() == [50., 50.]
