"""Performance statistics from completed account/trade histories only."""
import math
import numpy as np
import pandas as pd


def calculate_metrics(equity: pd.DataFrame, trades: pd.DataFrame, initial_cash: float,
                      annualization_factor: int, risk_free_rate: float, *, metrics_timezone='UTC') -> dict:
    if equity.empty or initial_cash <= 0:
        raise ValueError('Require account history and positive initial cash')
    if type(annualization_factor) is not int or annualization_factor <= 0:
        raise ValueError('annualization_factor must be a positive integer')
    if not math.isfinite(risk_free_rate) or risk_free_rate <= -1:
        raise ValueError('Invalid annual risk-free rate')
    if 'valuation_time' in equity or isinstance(equity.date.dtype, pd.DatetimeTZDtype):
        equity = daily_equity_snapshot(equity, initial_cash, metrics_timezone=metrics_timezone)
    returns = equity.daily_return.to_numpy(dtype=float)
    final = float(equity.equity.iloc[-1])
    years = (equity.date.iloc[-1] - equity.date.iloc[0]).days / 365.25
    total_return = final / initial_cash - 1
    cagr = (final / initial_cash) ** (1 / years) - 1 if years > 0 else None
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    volatility = std * math.sqrt(annualization_factor)
    excess = returns - ((1 + risk_free_rate) ** (1 / annualization_factor) - 1)
    sharpe = float(excess.mean() / std * math.sqrt(annualization_factor)) if std > 0 else None
    downside = math.sqrt(float(np.mean(np.minimum(excess, 0) ** 2)))
    sortino = float(excess.mean() / downside * math.sqrt(annualization_factor)) if downside > 0 else None
    maximum_drawdown = float(equity.drawdown.min())
    sells = trades.loc[trades.side == 'SELL']
    pnls = sells.realized_pnl.to_numpy(dtype=float)
    wins, losses = pnls[pnls > 0], pnls[pnls < 0]
    holding_days, entry_date = [], None
    for trade in trades.itertuples(index=False):
        if trade.side == 'BUY':
            entry_date = trade.execution_date
        elif entry_date is not None:
            holding_days.append((trade.execution_date - entry_date).days)
            entry_date = None
    return {
        'initial_cash': float(initial_cash), 'final_equity': final,
        'total_return': total_return, 'cagr': cagr,
        'annualized_volatility': volatility, 'sharpe_ratio': sharpe,
        'sortino_ratio': sortino, 'maximum_drawdown': maximum_drawdown,
        'calmar_ratio': cagr / abs(maximum_drawdown) if cagr is not None and maximum_drawdown < 0 else None,
        'trade_count': len(trades), 'closed_trade_count': len(sells),
        'open_position_quantity': int(equity.position_quantity.iloc[-1]),
        'win_rate': len(wins) / len(pnls) if len(pnls) else None,
        'profit_factor': float(wins.sum() / abs(losses.sum())) if len(losses) else None,
        'average_profit_per_trade': float(wins.mean()) if len(wins) else None,
        'average_loss_per_trade': float(losses.mean()) if len(losses) else None,
        'average_holding_period_days': float(np.mean(holding_days)) if holding_days else None,
        'total_commission': float(trades.commission.sum()),
        'total_slippage_cost': float(trades.slippage_cost.sum()),
        'turnover': float(trades.trade_value.sum() / equity.equity.mean()),
    }


def daily_equity_snapshot(equity, initial_cash, *, metrics_timezone='UTC'):
    """Last known valuation per local day; risk uses daily returns, never bar returns.

    A valuation exactly at midnight belongs to that new calendar day. No missing
    day is filled. The day boundary/timezone is part of the experiment audit.
    """
    from zoneinfo import ZoneInfo
    ZoneInfo(metrics_timezone)
    time_column = 'valuation_time' if 'valuation_time' in equity else 'date'
    times = pd.to_datetime(equity[time_column])
    if not isinstance(times.dtype, pd.DatetimeTZDtype) or times.isna().any():
        raise ValueError('Intraday valuations require timezone-aware timestamps')
    if not times.is_monotonic_increasing or times.duplicated().any():
        raise ValueError('Valuations must be strictly chronological')
    local_days = times.dt.tz_convert(metrics_timezone).dt.tz_localize(None).dt.normalize()
    frame = equity.copy()
    frame['_day'] = local_days
    result = frame.groupby('_day', sort=True).tail(1).reset_index(drop=True)
    result['date'] = result.pop('_day').astype('datetime64[ns]')
    previous = result.equity.shift(1).fillna(initial_cash)
    result['daily_return'] = result.equity / previous - 1
    peak = result.equity.cummax().clip(lower=initial_cash)
    result['drawdown'] = result.equity / peak - 1
    return result
