"""Construct price coordinates from exact bar-date factors; never fill missing factors."""
import pandas as pd
from src.data.schema import PRICE_COLUMNS, PRICE_BASES
from src.data.validation import validate_bars, validate_adjustments


def adjust_bars(bars, adjustments=None, method='qfq', *, anchor_end=None):
    validate_bars(bars)
    if method not in PRICE_BASES:
        raise ValueError(f'Unknown price basis: {method}')
    if method == 'raw':
        return bars.copy(deep=True)
    if adjustments is None:
        raise ValueError(f'Adjustment data unavailable for {method}')
    validate_adjustments(adjustments)
    selected = bars[['date', 'symbol']].merge(adjustments, on=['date', 'symbol'], how='left', validate='one_to_one')
    if selected.adj_factor.isna().any():
        raise ValueError('Missing adjustment factor for bar date')
    expected = 'provider_adjusted_close_ratio' if method == 'provider_adjusted' else 'cumulative_adjustment_factor'
    if not selected.factor_semantics.eq(expected).all():
        raise ValueError(f'{method} requires factor_semantics={expected}; provider factor scales are not interchangeable')
    factor = selected.adj_factor.copy()
    if method == 'qfq':
        # Use the latest factor at/before requested end, including suspended
        # sessions, independently per symbol; never use a later factor.
        anchors = {}
        for symbol, group in selected.groupby('symbol'):
            cutoff = pd.Timestamp(anchor_end) if anchor_end is not None else group.date.max()
            if cutoff.tzinfo is not None or cutoff != cutoff.normalize() or cutoff < group.date.max():
                raise ValueError('qfq anchor_end must be a session date at/after supplied bars')
            known = adjustments.loc[adjustments.symbol.eq(symbol) & (adjustments.date <= cutoff)]
            anchors[symbol] = known.adj_factor.iloc[-1]
        factor = factor / selected.symbol.map(anchors)
    # hfq intentionally uses the provider's absolute cumulative scale, matching
    # Tushare pro_bar. It does NOT rebase to the first requested date.
    adjusted = bars.reset_index(drop=True).copy(deep=True)
    adjusted[PRICE_COLUMNS] = adjusted[PRICE_COLUMNS].mul(factor.to_numpy(), axis=0)
    validate_bars(adjusted)
    adjusted.attrs['price_basis'] = method
    return adjusted
