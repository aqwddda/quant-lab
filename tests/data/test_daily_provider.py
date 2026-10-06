from datetime import date
import pytest
from src.data.providers._daily import check_daily_date_request
from src.data.providers.yahoo import YahooProvider
from src.data.providers.tushare import TushareProvider
from src.market import AssetClass, Timeframe


def test_daily_request_returns_inclusive_dates():
    assert check_daily_date_request('AAPL', '2020-01-01', '2020-01-01') == (
        date(2020, 1, 1), date(2020, 1, 1))


@pytest.mark.parametrize('symbol,start,end,frequency', [
    ('../AAPL', '2020-01-01', '2020-01-02', '1d'),
    ('AAPL', '2020-01-02', '2020-01-01', '1d'),
    ('AAPL', '2020-01-01', '2020-01-02', '15m'),
    ('AAPL', '2020-02-30', '2020-03-01', '1d'),
])
def test_daily_request_rejects_invalid_requests(symbol, start, end, frequency):
    with pytest.raises(ValueError):
        check_daily_date_request(symbol, start, end, frequency)


@pytest.mark.parametrize('provider', [YahooProvider, TushareProvider])
def test_supplier_capabilities_remain_daily_equity(provider):
    assert provider.capabilities.asset_classes == frozenset({AssetClass.EQUITY})
    assert provider.capabilities.timeframes == frozenset({Timeframe.D1})
    provider.capabilities.require(AssetClass.EQUITY, Timeframe.D1)
    for asset_class in AssetClass:
        for timeframe in Timeframe:
            if (asset_class, timeframe) != (AssetClass.EQUITY, Timeframe.D1):
                with pytest.raises(NotImplementedError):
                    provider.capabilities.require(asset_class, timeframe)
