import pandas as pd
import pytest
import tushare
from src.data.adjustment import adjust_bars
from src.data.normalize import normalize_tushare, normalize_yahoo
from src.data.providers.tushare import TushareProvider
from src.data.providers.yahoo import YahooProvider
from src.data.loader import load_bars
from tests.data.test_tushare_provider import FakeTushare
from tests.data.test_yahoo_provider import FakeYahoo


def split_fixture(monkeypatch):
    monkeypatch.setenv('TUSHARE_TOKEN', 'fixture-token')
    client = FakeTushare()
    snapshot = TushareProvider(client=client).fetch_snapshot('000001.SZ', '2020-01-02', '2020-01-03')
    return client, snapshot, normalize_tushare(snapshot.prepared, '000001.SZ')


def test_split_continuity_and_absolute_hfq_scale(monkeypatch):
    _, _, frames = split_fixture(monkeypatch)
    raw = frames['bars']
    assert raw.close.tolist() == [100., 50.]
    qfq = adjust_bars(raw, frames['adjustments'], 'qfq')
    hfq = adjust_bars(raw, frames['adjustments'], 'hfq')
    assert qfq.close.tolist() == [50., 50.]
    assert hfq.close.tolist() == [200., 200.]
    assert qfq.volume.equals(raw.volume) and qfq.amount.equals(raw.amount)


def test_cash_dividend_ratio():
    bars = pd.DataFrame({'date': pd.to_datetime(['2020-01-02', '2020-01-03']).astype('datetime64[ns]'),
        'symbol': 'SPY', 'open': [100., 99.], 'high': [101., 100.], 'low': [99., 98.],
        'close': [100., 99.], 'volume': [1000, 1000]})
    factors = bars[['date', 'symbol']].copy()
    factors['adj_factor'] = [0.99, 1.]
    factors['provider'] = 'yahoo'
    factors['factor_semantics'] = 'provider_adjusted_close_ratio'
    adjusted = adjust_bars(bars, factors, 'provider_adjusted')
    assert adjusted.close.tolist() == [99., 99.]
    assert bars.close.tolist() == [100., 99.]


def test_yahoo_reproduces_provider_adjusted_close():
    snapshot = YahooProvider(client=FakeYahoo()).fetch_snapshot('AAPL', '2020-08-28', '2020-08-31')
    frames = normalize_yahoo(snapshot.prepared, 'AAPL')
    adjusted = adjust_bars(frames['bars'], frames['adjustments'], 'provider_adjusted')
    assert adjusted.close.tolist() == snapshot.prepared['bars']['Adj Close'].tolist()
    with pytest.raises(ValueError, match='factor_semantics'):
        adjust_bars(frames['bars'], frames['adjustments'], 'qfq')


@pytest.mark.parametrize('method', ['qfq', 'hfq'])
def test_against_actual_tushare_pro_bar_sdk_offline(monkeypatch, method):
    client, _, frames = split_fixture(monkeypatch)
    # Official SDK computes against the same deterministic fake API, no network.
    expected = tushare.pro_bar(ts_code='000001.SZ', api=client, start_date='20200102',
                              end_date='20200103', adj=method, ma=[], retry_count=1)
    assert expected is not None
    actual = adjust_bars(frames['bars'], frames['adjustments'], method)
    for column in ['open', 'high', 'low', 'close']:
        comparison = expected.sort_values('trade_date')[column].to_numpy()
        # SDK rounds prices to 2 decimals; our layer retains precision.
        assert actual[column].to_numpy() == pytest.approx(comparison, abs=0.0051)


def test_qfq_anchor_uses_requested_end_not_future_dataset_end(monkeypatch, store):
    _, snapshot, frames = split_fixture(monkeypatch)
    store.save_dataset(**frames, dataset_id='tushare_anchor', provider='tushare',
        provider_version='fixture', market='CN', asset_type='EQUITY', start='2020-01-02', end='2020-01-03',
        source_frames=snapshot.source_frames)
    loaded = load_bars('CN', ['000001.SZ'], '2020-01-02', '2020-01-02', price_basis='qfq', store=store)
    assert loaded.close.tolist() == [100.]


def test_missing_factor_fails(monkeypatch):
    _, _, frames = split_fixture(monkeypatch)
    with pytest.raises(ValueError, match='Missing adjustment'):
        adjust_bars(frames['bars'], frames['adjustments'].iloc[1:], 'qfq')
