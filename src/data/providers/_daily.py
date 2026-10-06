"""Date-only request checks for Yahoo/Tushare daily Equity providers."""
from datetime import date
from src.data.manifest import safe_component


def check_daily_date_request(symbol, start, end, frequency='1d'):
    safe_component(symbol)
    if frequency != '1d':
        raise ValueError('Only daily frequency 1d is supported')
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if first.isoformat() != start or last.isoformat() != end:
        raise ValueError('Dates must use YYYY-MM-DD format')
    if first > last:
        raise ValueError('start must not exceed end')
    return first, last
