# Minimal Strategy V1

## 1. 目的

这是一个用于验证量化研究完整链路的测试策略。

目标不是追求盈利，而是验证以下模块能够正确工作：

数据读取  
→ 指标计算  
→ 信号生成  
→ 下一交易日成交  
→ 手续费与滑点  
→ 仓位变化  
→ 每日净值  
→ 交易流水  
→ 绩效指标  
→ Benchmark 对比  
→ Look-ahead Bias 检查  
→ 参数稳定性测试  
→ Walk-Forward 测试

---

# 2. 市场与标的

市场：

美股

标的：

SPY

数据频率：

日线 Daily Bar

需要的数据字段：

date
open
high
low
close
volume

使用复权后的历史价格数据。

---

# 3. 初始资金

initial_cash = 100000 USD

不使用杠杆。

不允许做空。

现金允许闲置。

只允许持有：

SPY
或
现金

---

# 4. 技术指标

计算两个简单移动平均线。

fast_ma：

过去 20 个交易日的收盘价简单平均值。

公式：

fast_ma[t] = mean(close[t-19:t])

slow_ma：

过去 60 个交易日的收盘价简单平均值。

公式：

slow_ma[t] = mean(close[t-59:t])

只有拥有至少 60 个交易日历史数据之后才能产生交易信号。

---

# 5. 买入规则

在 T 日收盘之后：

如果：

fast_ma[T] > slow_ma[T]

并且当前没有持仓，

则产生：

BUY SIGNAL

注意：

T 日收盘数据只能在 T 日收盘之后确定。

因此不能按照 T 日 close 成交。

实际买入发生在：

T+1 交易日 OPEN。

---

# 6. 卖出规则

在 T 日收盘之后：

如果：

fast_ma[T] <= slow_ma[T]

并且当前持有 SPY，

则产生：

SELL SIGNAL

实际卖出发生在：

T+1 交易日 OPEN。

---

# 7. 仓位规则

买入时：

使用当前可用现金的 100% 买入 SPY。

不允许融资。

只能购买整数股。

因此：

quantity = floor(
    available_cash /
    estimated_execution_cost_per_share
)

必须确保：

股票成交金额
+
手续费
+
滑点成本

不能超过当前现金。

卖出时：

卖出当前全部 SPY 持仓。

---

# 8. 成交模型

所有信号：

T 日 Close 后产生。

所有订单：

T+1 日 Open 成交。

不得使用 T+1 日 High、Low、Close 信息决定是否交易。

---

# 9. 滑点

默认：

slippage_rate = 0.0002

即：

0.02%

买入成交价格：

execution_price =
next_open × (1 + slippage_rate)

卖出成交价格：

execution_price =
next_open × (1 - slippage_rate)

---

# 10. 手续费

默认：

commission_rate = 0.0005

即：

0.05%

手续费：

commission =
trade_value × commission_rate

暂时不考虑最低手续费。

---

# 11. 每日资产计算

每个交易日结束后计算：

cash

position_quantity

position_market_value

equity

其中：

position_market_value =
position_quantity × close

equity =
cash + position_market_value

每日收益：

daily_return =
equity[t] / equity[t-1] - 1

历史最高净值：

running_max_equity =
max(equity[0:t])

回撤：

drawdown =
equity / running_max_equity - 1

---

# 12. 第一笔交易

因为 slow_ma 使用 60 日数据：

前 59 个交易日不能交易。

第 60 个交易日收盘后首次允许产生信号。

如果：

fast_ma > slow_ma

则：

第 61 个交易日开盘买入。

---

# 13. Benchmark

Benchmark：

SPY Buy & Hold

Benchmark 规则：

在策略第一个可以交易的日期买入 SPY。

之后一直持有到回测结束。

Benchmark 需要使用和策略一致的：

初始资金
手续费
滑点

同时输出策略和 Benchmark 净值曲线。

---

# 14. 输出交易流水

trades.csv 至少包含：

signal_date

execution_date

symbol

side

signal_close

fast_ma

slow_ma

raw_open

execution_price

quantity

trade_value

commission

slippage_cost

cash_before

cash_after

position_before

position_after

---

# 15. 输出每日账户状态

equity.csv 至少包含：

date

open

close

fast_ma

slow_ma

signal

cash

position_quantity

position_market_value

equity

daily_return

drawdown

---

# 16. 核心绩效指标

至少计算：

Total Return

CAGR

Annualized Volatility

Sharpe Ratio

Sortino Ratio

Maximum Drawdown

Calmar Ratio

Trade Count

Win Rate

Profit Factor

Average Profit Per Trade

Average Loss Per Trade

Average Holding Period

Total Commission

Total Slippage Cost

Turnover

同时输出：

Strategy

Benchmark

两者指标。

---

# 17. 正确性要求

禁止以下实现。

错误示例：

使用 T 日 Close 计算 fast_ma 和 slow_ma，

然后又按照 T 日 Close 成交。

正确实现：

T 日 Close

→ 计算 MA

→ 产生 signal

→ T+1 Open 执行。

禁止 Strategy 使用未来数据。

禁止：

shift(-1)

未来收益

未来最高价

未来最低价

center=True rolling

或者任何形式的未来价格。

---

# 18. 单元测试

创建一个至少 100 天的人造价格数据。

另外创建一个非常小的人工交易测试。

例如：

初始现金：

10000

已知：

买入信号日期

第二天 Open

卖出信号日期

第二天 Open

手续费

滑点

人工计算：

买入数量

买入手续费

剩余现金

卖出收入

卖出手续费

最终现金

最终 PnL

程序输出必须和人工结果一致。

---

# 19. Future Mutation Test

选择一个日期 T。

第一次：

使用完整历史数据计算截至 T 日的所有信号。

然后：

随机修改 T+1 以后全部：

open
high
low
close
volume

再次运行策略。

要求：

T 日以及之前的：

fast_ma

slow_ma

signal

必须与第一次完全一致。

否则认为存在未来数据泄露。

---

# 20. 参数稳定性测试

基础参数：

fast_window = 20

slow_window = 60

测试：

fast_window:

10
15
20
25
30

slow_window:

40
50
60
80
100

要求：

运行全部组合。

不要只输出收益最高的参数。

输出所有组合的：

CAGR

Sharpe

Max Drawdown

Total Return

Trade Count

生成参数热力图。

目标是观察策略表现是否存在相对稳定的区域。

---

# 21. 交易成本压力测试

至少测试：

Scenario 1

commission = 0.05%
slippage = 0.02%

Scenario 2

commission = 0.10%
slippage = 0.02%

Scenario 3

commission = 0.05%
slippage = 0.10%

Scenario 4

commission = 0.10%
slippage = 0.10%

比较：

CAGR

Sharpe

Max Drawdown

Total Return

---

# 22. 时间分段测试

分别统计不同年份：

annual return

max drawdown

trade count

用于观察收益是否只来自某几个年份。

---

# 23. Walk-Forward

第一版使用固定参数：

20 / 60

先跑完整回测。

之后再增加 Walk-Forward 参数优化。

例如：

训练 5 年

测试 1 年

滚动进行。

训练区间可以选择参数。

测试区间禁止重新选择参数。

最后只把所有测试区间拼接起来形成：

Out-of-Sample Equity Curve。

---

# 24. 最重要的原则

这个项目的目的不是证明 20/60 均线策略赚钱。

它只是用于验证：

量化回测系统是否正确。

因此：

如果回测亏钱，不要修改实现让结果变好。

如果测试失败，不要修改测试预期。

如果 Strategy 和账户结果不一致，优先检查：

时间对齐

成交时点

手续费

滑点

仓位计算

现金计算

未来数据泄露。
