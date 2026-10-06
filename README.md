# Quant Lab：可审计的市场数据与结构研究

当前支持 V1/V2 冻结日线兼容读取、V3 多资产类别/周期数据、本地 Forex 文件导入、锚定重采样、增量 Chan 包含/分型/笔，以及策略接口驱动的单标的 Equity 回测。
默认实验仍是原冻结 SPY SMA20/60，T 收盘信号、T+1 开盘成交。Chan-FX 只有结构观察，Forex 执行与最终买卖规则未实现。

- [架构与数据/时钟边界](docs/architecture.md)
- [Chan-Core 规则、确认状态与待确认清单](docs/chan-core.md)
- [本轮实施方案](docs/Quant%20Lab%20下一阶段重构与%20Chan-Core%20自研实施方案.md)
- [本轮验收记录](docs/重构与Chan-Core验收记录.md)
- [V2 数据语义与历史验收](docs/数据层V2开发与验收记录.md)
- [项目教程](docs/项目教程.md)：V1 实验教学；旧 `src.*` 调用兼容，当前代码位置以架构文档为准。

## 环境

```bash
conda activate quant-lab
python --version  # Python 3.11
python -m pip install -r requirements-lock.txt
python -m pip install -e . --no-deps --no-build-isolation
python -m pytest -q
python scripts/run_backtest.py
```

使用已有 Conda 环境，不创建额外虚拟环境。脚本不做路径注入；editable 安装后可从其它工作目录执行脚本。
新增结构与数据功能使用已有依赖，不需要第三方 Chan 库或联网 FX SDK。

## 默认冻结回归

`data/raw/spy_daily.parquet` SHA-256：`bdd34d3bc950d433a5eeeaa594be558dd1c920dacbd61f8750366d8836bca19f`。
2766 行，2015-01-02..2025-12-31；45 次策略成交、1 次 benchmark 成交。
策略总收益 1.466718879583301、CAGR 0.08558235360852229；benchmark 总收益 2.9389675730204616、CAGR 0.13278961489741126。
该冻结文件不分发到 Git，重新下载不能替代原回归数据。缺少文件时对应测试明确 skip，不能据此声称完成真实 SPY 验收。

默认配置：

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
  price_basis: legacy_provider_adjusted
  market: US
```

历史 flat strategy YAML 继续兼容。backtest.yaml 管资金、成本、区间和输出，data.yaml 管存储与供应商启用，不存 token。

## 数据流程与版本

```text
Provider → Source Snapshot → Normalization → Validation
         → Frozen Store / Manifest / SHA → Local Loader → Bar
         → Structure / Strategy → Orders → Execution → Portfolio → Metrics
```

V1 `data/raw/` 与 V2 原有路径和 Manifest 保持不变。新 CLI 下载发布 schema_version=3：

```text
data/source/{provider}/{dataset_id}/
data/normalized/bars/{asset_class}/{venue}/{timeframe}/{symbol}/{dataset_id}/bars.parquet
data/manifests/{dataset_id}.json
data/manifests/{dataset_id}.json.sha256
```

版本不可覆盖，不使用可变 latest 指针。离线读取不下载缺失文件，不填值/去重/修复；重叠 V2 版本必须指定 ID，V3 读取总是显式 ID。
Source Data 指供应商响应快照，不能据此认定它就是历史未复权价格。

V3 必需 UTC `timestamp, symbol, open, high, low, close`，timestamp 语义为 bar_start。
`volume, tick_volume, amount, open_interest` 可缺省；不把无真实成交量的 Forex 填为零。周期支持 1m、5m、15m、30m、1h、4h、1d。
Instrument 区分资产类别、venue、canonical symbol 和 provider_symbol。可存期货数据/元信息，但期货执行账户未实现。

V2 日线 date 是无时区的本地 session 标签，不是 UTC。V2→UTC 读取必须显式给 session_timezone；新的 Yahoo/Tushare 日线 V3 也记录午夜 session 坐标假设，不推断实际 intraday 开闭市时间。

## Yahoo / Tushare

```bash
python scripts/download_data.py --provider yahoo --market US --symbol AAPL --start 2015-01-01 --end 2025-12-31 --frequency 1d
export TUSHARE_TOKEN='your-token'
python scripts/download_data.py --provider tushare --market CN --symbol 000001.SZ --start 2015-01-01 --end 2025-12-31 --frequency 1d
```

SDK 的 capabilities 如实声明：本期 Yahoo 为 US equity daily，Tushare 为 CN equity daily；声明不等于支持所有 AssetClass/Timeframe。Tushare token 只从环境读取，不写文件、不调用 set_token。真实 Tushare 验收仍受 token/账户权限约束。
Yahoo source `auto_adjust=False` OHLC 仍包含拆股缩放；normalization 用全部冻结后续拆股显式反向还原 raw OHLC、volume 与 dividend。Tushare vol 手×100→股，amount 千元×1000→CNY。已有 V2 因子与事件语义沿用。

| price_basis | 定义 |
| --- | --- |
| raw | 经明确 normalization 的历史未复权 OHLC；账户尚不处理公司行动 |
| provider_adjusted | Yahoo raw × Adj Close / reconstructed raw Close |
| qfq | Tushare raw × cumulative factor / 请求结束日及之前的最新 factor；含停牌日 anchor |
| hfq | raw × absolute cumulative factor，不按区间首日重新缩放 |
| legacy_provider_adjusted | 直接使用原冻结 V1 auto_adjust=True 数据 |

缺失因子或错误 factor_semantics 明确失败；不混用 Yahoo ratio 与 Tushare cumulative factor。复权坐标是 synthetic account，无额外分红现金/拆股 quantity 处理。
这些是下载时快照，不能证明供应商历史坐标在原时间点可得；其修订/漏项仍可能存在。

## 本地 Forex 导入

```bash
python scripts/download_data.py --provider local --input /path/to/EURUSD.csv \
  --symbol EURUSD --provider-symbol EURUSD.a --asset-class forex --venue broker_x \
  --frequency 15m --source-timezone UTC --timestamp-semantics bar_start
```

CSV/Parquet 列使用 timestamp/open/high/low/close；symbol 若存在必须匹配 provider_symbol。原始字节、解析表、来源元数据都冻结，再执行 normalization/validation/store/manifest。Naive 来源必须按声明时区解释；bar_end 显式减去固定周期得到 bar_start。
只有供应商 tick count 时可提供 tick_volume，不提供 volume。真实成交量/金额/持仓单位由来源声明，程序不猜测。没有假造在线 FX 数据源。

## 离线读取与重采样

```bash
python scripts/verify_dataset.py --dataset-id <id>
python scripts/inspect_data.py --dataset-id <id>
python scripts/verify_dataset.py --legacy-path data/raw/spy_daily.parquet
python scripts/resample_data.py --source-dataset-id <1m-id> --dataset-id <new-4h-id> \
  --target-timeframe 4h --aggregation-timezone UTC --anchor 00:00
```

聚合要求完整窗口，不补缺失、不丢弃首尾 partial；时区、anchor、父版本与 SHA、聚合规则进入 lineage。DST 不确定/变长窗口明确失败。

```python
from quant_lab.data.loader import load_dataset, iter_bars

frame = load_dataset('explicit_id', symbols=['EURUSD'], timeframe='15m')
for bar in iter_bars(frame):
    print(bar.timestamp, bar.available_at)

# V2 compatibility:
from quant_lab.data.loader import load_bars
bars = load_bars('US', ['SPY', 'AAPL'], '2020-01-01', '2025-12-31',
                 price_basis='raw', dataset_id={'SPY': 'spy-v2-id', 'AAPL': 'aapl-v2-id'})
```

## Chan 观察

```bash
python scripts/inspect_chan.py --dataset-id <id> --symbol EURUSD --plot
python scripts/run_backtest.py --strategy-config config/chan_fx.yaml \
  --backtest-config /path/to/observation-range.yaml --dataset-id <15m-fx-id> --observe-only
```

导出 raw_bars、merged_bars、fractals、strokes CSV 和 chan.json；inspect 的 --plot 生成静态 chan.png。
默认初始包含没有方向时报错；显式 up/down 是临时实验策略。等高/等低分型严格排除，端点相等不替换，gap 不增加距离。confirmed_at 与 pivot_time 分开，confirmed 笔不可回写，最后 tentative 可以延伸。
不实现最终 Chan 买卖规则，也不输出虚假的 FX 收益。

## 回测与报告

```bash
python scripts/run_backtest.py --strategy-config /path/to/equity-strategy.yaml \
  --backtest-config /path/to/backtest.yaml --dataset-id <v2-or-v3-id>
```

V3 Equity 可使用分钟线；单标的、long/cash、整数股、全现金分配、下一可用开盘成交。
Benchmark 在策略预热后的首次可成交开盘尝试买入一次。末根信号不成交，不强制期末平仓。
滑点进入 execution_price，trade_value=quantity×execution_price，commission 单独扣除，slippage_cost 不二次扣现金。

完成回测输出 trades.csv、equity.csv、metrics.json、equity_curve.png、drawdown.png，另有 benchmark 两份 CSV。
V3 保存逐 bar 净值、bar_return、valuation_time，风险指标用 UTC 日末已知净值重算日收益；报告记录 metrics_frequency=daily。历史 V1 CSV 的列、数值与哈希保留。
报告审计包含配置、版本、Manifest/SHA、源码 SHA、环境和假设。数据、报告、缓存与凭据不进 Git。

## 边界

CN Equity 仍是 smoke：未建模完整 A 股 T+1、涨跌停、整手、停牌撮合和税费。Corporate action 存储但不应用于账户。
US/CN 日历缺漏与来源准确性限制沿用 V2。不存在完整 FX broker simulation、期货账户、多资产组合、实盘、ML、参数优化、数据库或实时框架。
