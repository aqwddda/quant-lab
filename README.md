# Quant Lab

Quant Lab 是用于多资产、多周期量化研究的实验工程。核心模块是 `data`、`market`、`chan`、`strategies`、`backtest`，真实实现直接位于 `src/*`。

支持不可变市场数据、Yahoo/Tushare/Local Provider、锚定重采样、增量 Chan 结构和单标的 Equity 回测。当前目标是验证研究基础设施的正确性，不是实盘交易或发现 alpha。

- [架构与时钟边界](docs/architecture.md)
- [Chan-Core 规则和待确认项](docs/chan-core.md)
- [SMA 策略与执行约定](docs/strategy_spec.md)
- [项目教程](docs/项目教程.md)

## 环境与测试

```bash
conda activate quant-lab
python --version  # Python 3.11
python -m pip install -r requirements-lock.txt
python -m pytest -q
```

使用现有 Conda 环境，不创建新的虚拟环境。脚本可直接从项目根目录运行；也可用绝对路径从其它工作目录运行。可选 `python -m pip install -e . --no-deps --no-build-isolation` 只安装当前 `src` 包，脚本不依赖这一步。

## 源码职责

| 路径 | 职责 |
| --- | --- |
| `src/market/` | AssetClass、Timeframe、不可变 Bar/Instrument |
| `src/data/` | 来源冻结、normalization、校验、Manifest/SHA、Store/Loader、重采样 |
| `src/chan/` | 包含、严格顶底分型、笔、tentative/confirmed 状态 |
| `src/strategies/` | Strategy Protocol、SMA 信号、Chan-FX 观察骨架 |
| `src/backtest/` | 时间推进、执行价格/成本、Equity 账户、日频绩效 |
| `src/validation.py` | 未来变异与因果性检查 |

统一 `from src...` 导入。每项能力只有一个正式路径，不维护其它源码入口。

## 正式数据模型

只支持 `schema_version=3` 的 Manifest。Canonical bars 必需字段：`timestamp, symbol, open, high, low, close`。timestamp 必须 UTC aware、语义为 bar_start。
可选 `volume, tick_volume, amount, open_interest`；缺少代表未知，不补零。支持 1m、5m、15m、30m、1h、4h、1d。
`src.market.Instrument` 是唯一 canonical Instrument，区分 `asset_class, venue, symbol, provider_symbol`，支持 currency、tick_size、lot_size、contract_multiplier、expiry 等元信息；资产类别包括 equity、forex、futures。期货数据/元信息可存储，期货执行账户未实现。
Yahoo/Tushare 原始证券信息先冻结到 Source Snapshot，归一化直接生成 `list[Instrument]`，正式字段只保存在 `manifest["instruments"]`，不再保存 normalized instrument parquet。Local 使用研究者显式提供的同一 Instrument。

```text
Provider → Source Snapshot → Normalization → Validation
         → Frozen Store / Manifest / SHA → Local Loader → Bar
         → Structure / Strategy → Execution → Portfolio → Metrics
```

```text
data/source/{provider}/{dataset_id}/
data/normalized/bars/{asset_class}/{venue}/{timeframe}/{symbol}/{dataset_id}/bars.parquet
data/manifests/{dataset_id}.json
data/manifests/{dataset_id}.json.sha256
```

Supplier Source 是原响应快照，不等于 Raw Price。版本拒绝覆盖，Manifest 最后发布，Loader 显式选择 dataset ID，只读本地，不下载、不修复、不去重、不填值。

## 下载与本地导入

```bash
python scripts/download_data.py --provider yahoo --market US --symbol SPY \
  --start 2015-01-01 --end 2025-12-31 --frequency 1d

export TUSHARE_TOKEN='your-token'
python scripts/download_data.py --provider tushare --market CN --symbol 000001.SZ \
  --start 2015-01-01 --end 2025-12-31 --frequency 1d

python scripts/download_data.py --provider local --input /path/to/EURUSD.csv \
  --symbol EURUSD --provider-symbol EURUSD.a --asset-class forex --venue broker_x \
  --frequency 15m --source-timezone UTC --timestamp-semantics bar_start
```

Yahoo/Tushare 只声明 `AssetClass.EQUITY + Timeframe.D1` 能力；日期请求检查由 `src/data/providers/_daily.py` 的 `check_daily_date_request` 负责。通用 Provider Base 只保留能力声明和协议。SDK 仅供下载流程使用；Tushare token 只读环境变量。
LocalBarProvider 显式导入 equity、forex、futures 的 1m、5m、15m、30m、1h、4h、1d 数据，使用调用者声明的 Instrument、时区和时间语义。
Yahoo OHLC 本身有拆股调整，使用冻结的全部后续 split 显式反向还原 raw OHLC/volume/dividend。Tushare vol 手×100→股、amount 千元×1000→CNY。
Daily supplier session 标签在 normalization 内转为 UTC 午夜坐标，并保留 date 作为辅助因子键；午夜不是实际交易所开盘时刻，不能据此推导分钟线 session schedule。

| price_basis | 定义 |
| --- | --- |
| raw | 经审计 normalization 的历史未复权价格 |
| provider_adjusted | Yahoo raw × Adj Close / reconstructed raw Close |
| qfq | raw × cumulative factor / 本次请求结束日及之前的最新 factor |
| hfq | raw × absolute cumulative factor，不重新缩放首日坐标 |

因子必须覆盖 exact session key，不混用 Yahoo ratio 和 Tushare cumulative factor。qfq 保留停牌日 anchor，不使用请求结束之后的因子。
Local CSV/Parquet 使用 timestamp/open/high/low/close，symbol 若存在必须匹配 provider_symbol。冻结原文件字节、解析表和请求信息，再校验发布。声明时区解释 naive 时间；bar_end 减去固定周期转为 bar_start。没有真实 Forex volume 时只提供 tick_volume。来源单位/完整性不由程序猜测。

## 校验、读取与重采样

```bash
python scripts/verify_dataset.py --dataset-id <id>
python scripts/inspect_data.py --dataset-id <id> --price-basis raw
python scripts/resample_data.py --source-dataset-id <1m-id> --dataset-id <new-id> \
  --target-timeframe 4h --aggregation-timezone UTC --anchor 00:00
```

重采样 OHLC 用 first/max/min/last，volume/tick_volume/amount 求和，open_interest 取末值。显式时区、anchor、父版本 SHA 和聚合规则进入 lineage。不完整、缺失或不确定 DST 窗口报错，不补齐、不丢弃。

```python
from src.data.loader import load_dataset, iter_bars
from src.chan import ChanAnalyzer

frame = load_dataset('explicit_id', symbols=['EURUSD'], timeframe='15m')
analyzer = ChanAnalyzer()
analyzer.extend(iter_bars(frame))
```

## Chan 观察

```bash
python scripts/inspect_chan.py --dataset-id <id> --symbol EURUSD --plot
python scripts/run_backtest.py --strategy-config config/chan_fx.yaml \
  --backtest-config /path/to/observation.yaml --dataset-id <id> --observe-only
```

导出 raw_bars、merged_bars、fractals、strokes 的 CSV 与 chan.json，可选静态 chan.png。
confirmed_at 与 pivot_time 分开，confirmed 笔不回写，最终 tentative 可以延伸。初始包含默认报错；显式 up/down 是实验选择。具体规则见 Chan 文档。
Chan-FX 只观察结构，不生成订单或 Forex 收益。未定义的买卖规则和 Forex 执行模型明确 NotImplemented。

## Equity 回测

默认 strategy.yaml 为 SPY/SMA20/60/provider_adjusted 日线，必须显式指定通过正式流程冻结的 dataset ID：

```bash
python scripts/run_backtest.py --dataset-id <spy-id>
python scripts/run_backtest.py --strategy-config /path/to/equity.yaml \
  --backtest-config /path/to/backtest.yaml --dataset-id <id>
```

目标在当前 bar 完成后生成，在下一可用开盘执行。整股、全现金、long/cash，两侧手续费和滑点。Benchmark 在预热后首次可执行开盘尝试买入一次。末根目标不成交，不强制期末平仓。

每次输出 trades.csv、equity.csv、metrics.json、equity_curve.png、drawdown.png，以及 benchmark 两份 CSV。
净值逐 bar 保存；风险指标使用 UTC 每天最后一个已知估值，报告记录 `metrics_frequency=daily`。审计包含配置、来源、Manifest/SHA、源码 SHA、环境和因果性检查。

CN 仍是 smoke，缺完整 A 股执行约束。Corporate action 事件不作用于账户。未实现 Forex/Futures 账户、多资产组合、实盘、机器学习或参数优化。数据、报告、缓存和凭据不进入 Git。
