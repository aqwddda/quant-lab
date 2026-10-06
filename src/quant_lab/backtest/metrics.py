"""Performance statistics from completed account/trade histories only."""
import math
import numpy as np
import pandas as pd


def calculate_metrics(equity: pd.DataFrame, trades: pd.DataFrame, initial_cash: float,
                      annualization_factor: int, risk_free_rate: float) -> dict:
    if equity.empty or initial_cash <= 0:
        raise ValueError('Require account history and positive initial cash')
    if type(annualization_factor) is not int or annualization_factor <= 0:
        raise ValueError('annualization_factor must be a positive integer')
    if not math.isfinite(risk_free_rate) or risk_free_rate <= -1:
        raise ValueError('Invalid annual risk-free rate')
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
