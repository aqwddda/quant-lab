"""Explicit supplier -> canonical conversion. Sorting happens only at this boundary."""
import numpy as np
import pandas as pd
from quant_lab.data.schema import (BAR_COLUMNS, PRICE_COLUMNS, ACTION_COLUMNS, INSTRUMENT_COLUMNS,
                             CALENDAR_COLUMNS, require_columns)
from quant_lab.data.validation import validate_bars, validate_adjustments


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




def daily_snapshot_v3(normalized, *, provider, session_timezone):
    """Explicit session-label -> UTC start adapter; original date remains for factors.

    Midnight is a session coordinate, not an assertion of actual exchange opening.
    This dataset does not supply an intraday exchange session schedule.
    """
    from quant_lab.market import Instrument, AssetClass
    bars = normalized['bars'].copy()
    bars['timestamp'] = bars.date.dt.tz_localize(session_timezone, ambiguous='raise',
        nonexistent='raise').dt.tz_convert('UTC')
    items = [Instrument(row.symbol, row.symbol, AssetClass.EQUITY, row.exchange,
        quote_currency=row.currency) for row in normalized['instruments'].itertuples()]
    return bars, items
