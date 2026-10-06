# SMA 策略与 Equity 研究约定

正式实现：`src/strategies/sma.py`；本策略用于验证研究基础设施，不以收益优劣判断工程正确性。

## 指标和目标

SmaCrossStrategy 默认 fast_window=20、slow_window=60，要求整数且 0<fast<slow。
每根已完成 Bar 的 close 进入有界滚动窗口，产生 fast_ma、slow_ma。
前 slow_window−1 根返回 TargetPosition(None)；预热完成后 fast>slow 返回1，fast≤slow 返回0。None 表示尚不可交易，0表示cash，1表示long。

```yaml
strategy:
  name: sma_cross
  params:
    fast_window: 20
    slow_window: 60

data:
  symbol: SPY
  asset_class: equity
  timeframe: 1d
  price_basis: provider_adjusted
  market: US
```

## 时序

T close 完成→计算 target→下一可用 bar open 执行。默认窗口首次可能成交于第61根 bar。
新 bar 的 high/low/close 不决定该 bar 开盘订单，末根信号没有下一开盘因而不成交。
不借款、不做空、不分批加仓、不强制期末平仓。

## 价格、成本与记账

BUY execution_price=raw_open×(1+slippage_rate)；SELL 为减号。
quantity=floor(cash / (execution_price×(1+commission_rate)))，另有浮点边界检查，现金不能负。
trade_value=quantity×execution_price，commission=trade_value×commission_rate。
slippage_cost=quantity×abs(execution_price−raw_open)，已经体现在成交价，不再扣一次现金。
成本基础包含买入手续费，卖出 realized_pnl 包含两侧成本。equity=cash+quantity×close。
使用调整价时 raw_open 指所选价格坐标的滑点前开盘；账户为 synthetic adjusted-price account，没有额外公司行动现金/持仓处理。

## Benchmark、报告和验证

Benchmark 在第一个可交易 open 尝试全现金买入一次，使用相同费用和初始现金。
每次报告保存账户/交易/指标和两张图，另有 benchmark CSV。日志可以手算复现单笔。
bar 净值逐根保留；风险统计基于每日最后估值，年化因子默认252，不能将分钟线收益直接乘252。

确定性测试覆盖：98股买入、92.102剩余现金、10753.6298最终现金、753.6298已实现损益，以及逐 bar 对账、首次成交、末根不成交、未来变异和下一开盘不依赖当日close。
不在本轮实现参数优化、Walk-Forward 或盈利寻优。
