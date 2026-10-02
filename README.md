# Quant Lab：最小可审计回测基础工程

仅用于 SPY 日线研究：20/60 简单均线、long/cash、无融资或做空。
遵循 `AGENTS.md`、`docs/基础工程.md` 和当前阶段的策略规范。

## 使用现有环境

```bash
conda activate quant-lab
python --version  # Python 3.11
python -m pip install -r requirements-lock.txt
python -m pytest -q
python scripts/download_data.py
python scripts/run_backtest.py
```

`requirements.txt` 列出直接依赖的兼容范围；`requirements-lock.txt` 固定本次验证环境的完整版本。
不要创建新的环境。冻结数据已存在时跳过下载命令；下载脚本拒绝覆盖已有文件。
两个脚本可以从任意工作目录执行，默认配置与数据路径相对项目根目录解析。

## 模块与时间线

| 文件 | 职责 |
| --- | --- |
| `src/data_loader.py` | 读取冻结 Parquet、计算 SHA-256，不联网 |
| `src/strategy.py` | 只计算历史收盘均线及目标仓位 |
| `src/execution.py` | 前一日目标在当日开盘执行、整数股、手续费与滑点 |
| `src/portfolio.py` | 现金、持仓、成本基础、已实现/未实现损益、净值 |
| `src/backtest.py` | 按交易日推进策略与 Benchmark |
| `src/metrics.py` | 已完成回测的绩效指标 |
| `src/validation.py` | 数据检查、未来变异及截断历史检查 |

第 60 个交易日收盘才有完整 slow_ma；第 61 个交易日开盘才可能首次成交。
策略目标 `target=-1` 表示未完成预热，`1` 表示持有，`0` 表示现金。
`signal` 是当日收盘根据当前持仓产生的 BUY/SELL/HOLD/WAIT；最后一日新信号不成交。
同日开盘成交不使用当天 high/low/close。当天 close 只用于收盘估值及次日目标。
Benchmark 在第 61 个交易日开盘买入一次，与策略首次实际买入信号是否出现无关。

## 数据与配置

`config/strategy.yaml` 设置标的和均线窗口；`config/backtest.yaml` 设置资金、成本、日期、路径及年化因子。
默认资金 100,000 USD、手续费 0.05%、单边滑点 0.02%，无风险年利率 0。

下载使用 Yahoo Finance/yfinance 的复权 OHLC，结束日期包含 2025-12-31。
数据文件为 `data/raw/spy_daily.parquet`，旁边的 `.metadata.json` 保存来源、复权设置、时间、日期范围与文件哈希。
每日日期是纽约交易所当地会话日期，移除时区前先转到 America/New_York，不把它当成 UTC 成交时间。
回测验证哈希，执行前后检查冻结文件一致，不重新下载、不排序修复、不补齐缺失值。
检查日期唯一/升序/非空、时区、周末、数值有限、正价格、OHLC 关系及非负整数成交量。
不独立验证交易所全部节假日，亦不能保证供应商未漏掉某个交易日。

## 账户与成本

买入：`execution_price = raw_open * (1 + slippage_rate)`。
卖出：`execution_price = raw_open * (1 - slippage_rate)`。
`trade_value = quantity * execution_price`，`commission = trade_value * commission_rate`。
`slippage_cost = quantity * abs(execution_price - raw_open)`，只作成本归因。
滑点已包含在成交金额中，不再次扣现金。

买入数量按 `floor(cash / (execution_price * (1 + commission_rate)))` 计算；买入扣成交金额和手续费，卖出增加成交金额减手续费。
成本基础包含买入手续费；已实现损益包含两侧手续费与成交价滑点。
现金不足一股时不产生虚构交易，也不允许负现金。

## 输出与指标口径

生成 `reports/trades.csv`、`equity.csv`、`metrics.json`、`equity_curve.png`、`drawdown.png`。
额外输出 `benchmark_trades.csv` 与 `benchmark_equity.csv`，便于独立复算基准。
`metrics.json` 包含配置、数据来源和哈希、源码哈希、运行依赖版本及未来变异检查日期。
数据、报告、缓存和秘密文件均被 Git 忽略；本项目不自动提交 Git。

- 总收益：期末净值 / 初始资金 - 1；CAGR 按首末日期间隔 / 365.25 计算，含现金预热期。
- 波动率：日收益样本标准差 × √252；Sharpe：日超额收益均值 / 日收益样本标准差 × √252。
- Sortino：日超额收益均值 / 全部日样本负超额收益的 RMS × √252。
- 回撤从初始资金开始维护历史最高净值；Maximum Drawdown 输出负数；Calmar=CAGR/回撤绝对值。
- Trade Count 是成交笔数；Closed Trade Count 是完整买卖往返次数。
- 胜率、Profit Factor、平均盈利/亏损及持有期只统计已平仓往返；持有期单位为日历天。
- Turnover 是累计双边成交金额 / 平均每日净值，不年化。
- 没有已平仓交易或分母为零的比率输出 JSON `null`，不输出 NaN/Infinity。

## 已知假设和边界

复权价格回测是合成价格账户，不是历史真实美元成交账本。
分红/拆股影响已进入复权价格，不重复增加分红现金；复权后价格上的整数股也不是严格的历史真实股数。
下载时的复权历史可能受后来公司行动及供应商修订影响，因此只对本次冻结数据复现结果。
future mutation test 验证程序因果性，不能证明供应商数据本身是历史时点可得的数据。

固定滑点、按比例手续费、全额开盘成交是假设；没有成交量限制、冲击模型、现金利息、税费或最低手续费。
回测期末不强制平仓，剩余持仓按复权收盘估值，不扣除假设清仓成本。
在基础正确性确认前，不增加参数优化、Walk-Forward、实盘、模拟盘或其他策略。
