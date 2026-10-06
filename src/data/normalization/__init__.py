"""Explicit supplier -> canonical conversion. Sorting happens only at this boundary."""
import numpy as np
import pandas as pd
from src.data.validation import validate_bars


def canonical_order(frame, keys=('date', 'symbol')):
    return frame.sort_values(list(keys), kind='stable').reset_index(drop=True)


def integer_volume(values):
    values = pd.to_numeric(values, errors='raise').to_numpy(dtype=float)
    nearest = np.rint(values)
    # Only binary floating point arithmetic noise, never fractional shares.
    if not np.isfinite(values).all() or (values < 0).any() or not np.allclose(values, nearest, rtol=0, atol=1e-6):
        raise ValueError('Volume must be finite, nonnegative and integer-valued after explicit unit conversion')
    if (nearest >= np.iinfo(np.int64).max).any():
        raise ValueError('Volume exceeds int64 range')
    return nearest.astype('int64')


DAILY_PRICE_COLUMNS = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume']


def normalize_session_bars(bars, session_timezone):
    """Normalize supplier session labels into the formal UTC bar schema.

    Midnight is a session coordinate, not an actual exchange opening timestamp.
    Date remains an auxiliary key for exact-session adjustment factors.
    """
    bars = bars.copy()
    bars['timestamp'] = bars.date.dt.tz_localize(session_timezone, ambiguous='raise',
        nonexistent='raise').dt.tz_convert('UTC')
    validate_bars(bars, '1d')
    return bars


def instruments_from_reference(reference):
    from src.market import Instrument, AssetClass
    return [Instrument(row.symbol, row.symbol, AssetClass.EQUITY, row.exchange,
        quote_currency=row.currency) for row in reference.itertuples()]
