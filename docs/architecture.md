# Quant Lab 当前架构

源码直接位于 `src/`，统一使用 `src.*`。不在源码根目录下再创建项目名包。

```mermaid
flowchart TD
    P[Yahoo / Tushare / Local] --> S[Source Snapshot]
    S --> N[Normalization]
    N --> V[Canonical UTC Bars / Validation]
    V --> F[Frozen Store / Manifest / SHA]
    F --> L[Offline Loader]
    L --> B[Market Bar]
    B --> C[Chan Structure]
    B --> T[Strategy]
    C --> T
    T --> O[TargetPosition]
    O --> E[Next Open Execution]
    E --> A[EquityPortfolio]
    A --> M[Daily Metrics / Reports]
```

## 职责与依赖

| 模块 | 职责 |
| --- | --- |
| `src/market/` | AssetClass、Timeframe、Bar、唯一 canonical Instrument；不依赖供应商或交易 |
| `src/data/providers/` | 供应商通信/本地文件，声明能力；SDK lazy import |
| `src/data/normalization/` | 时间、字段、单位、拆股反向还原；daily date 是来源辅助键 |
| `src/data/validation.py` | 当前 Canonical Bars、因子、公司行动、日历校验 |
| `src/data/manifest.py` / `store.py` | schema_version=3、身份、不可变保存、内容 SHA |
| `src/data/loader.py` | 显式版本读取、筛选、DataFrame→Bar |
| `src/data/resample.py` | 显式时区/anchor、完整聚合窗口、父版本 lineage |
| `src/chan/` | 增量包含/分型/笔；纯 Python，不导入数据层或绘图库 |
| `src/visualization/` | 只读 OHLC candle、merged range、分型/笔与 overlay PNG；复用已有结构 |
| `src/strategies/` | 当前已完成 Bar→不可变 TargetPosition；不管理账户 |
| `src/backtest/engine.py` | 推进时钟；不导入 SMA 或 Chan 专属实现 |
| `src/backtest/execution.py` | 成交价格/成本/constraints；Equity long/cash，FX 未定义 |
| `src/backtest/portfolio.py` | EquityPortfolio 的现金、持仓、损益 |
| `src/backtest/metrics.py` | 从完成结果计算 Daily Equity Snapshot 与绩效 |
| `src/validation.py` | Strategy/Chan 未来变异与确认时点因果性 |

## 正式数据

Canonical Bar 必需 UTC timestamp、symbol、OHLC；可选 volume/tick_volume/amount/open_interest。timestamp 语义为 bar_start，已知时间为 timestamp+固定 timeframe duration。
只维护 schema_version=3 Manifest，校验不支持的版本明确失败。date 可作为股票日线因子、公司行动或日历的 session key，不能替代 canonical timestamp。
Yahoo/Tushare 当前只供应 equity daily，daily session 午夜转 UTC 的假设写入 Manifest。Local 使用调用者指定的 source_timezone 与 bar_start/bar_end，aware offset 必须与声明一致。
Loader 明确 dataset ID，核验完整文件后才筛选；同一个版本可包含同一 asset_class/venue 的多标的，不代表多资产账户已实现。
原文件字节、响应表、request 元数据均可冻结；Manifest 由自身 SHA sidecar 保护，identity 独立冻结。

### Instrument 与 Provider 边界

`src.market.Instrument` 是唯一正式证券模型。Yahoo 的 `get_info()` 字典与 Tushare 的 `stock_basic` 响应表作为供应商原始 metadata 冻结；normalization 直接构造 `list[Instrument]`，下载入口将其交给 DataStore。正式字段保存在 `manifest["instruments"]`，并通过 `Instrument(**item)` 验证；不再维护 normalized instrument 表。

Yahoo exchange code 显式映射到 canonical venue：NMS/NGM/NCM→NASDAQ、NYQ→NYSE、PCX→NYSE_ARCA、ASE→NYSE_AMERICAN、BATS→CBOE_BZX，支持的 OTC code 归为 OTC。上市分层信息保留在 Source Snapshot。Tushare 通过显式映射得到 SZSE/SSE/BSE；未支持的 exchange 报错。供应商名称、上市/退市日期等信息留在 Source，不增加通用 Instrument 字段。

LocalBarProvider 接收研究者显式提供的同一 Instrument，冻结请求与原文件，通过其 symbol/provider_symbol 对齐 canonical bars；支持 equity/forex/futures 与 1m/5m/15m/30m/1h/4h/1d。

Provider Base 只包含 `ProviderCapabilities` 与 `BarProvider` 协议。Yahoo/Tushare 仍只声明 Equity + D1，日线日期检查在 `providers/_daily.py:check_daily_date_request`。Local 不依赖这一辅助模块，也不采用 US/CN 或 date-only 请求限制。

## 价格与窗口

raw OHLC 由 normalization 产生，供应商 Source 不等于 raw price。Yahoo 拆股反向还原与 Tushare 手/千元转换保持明确审计假设。
因子使用 exact session key；qfq 使用请求结束时点之前的最新 factor，hfq 保留累计绝对尺度。账户未处理公司行动。
重采样按明确 local anchor 的左闭右开窗口，固定周期必须整除目标周期。完整源网格才生成目标 bar；缺失、partial、DST 不确定/变长边界失败。目标 close 只在目标窗口关闭后可用。

## 回测时序与指标

Engine 在当前 open 执行上一完成 bar 的 target，再于当前 close 调用策略并估值。StrategyContext 只提供 index 和当前 available_at。
TargetPosition(None) 为不可交易，0 为 cash，1 为 long。diagnostics 不能覆盖账户或执行字段。
Equity 买入整股、全现金，卖出清仓；commission 单独扣款，slippage 已进入 execution_price，slippage_cost 仅作归因。
Benchmark 在预热后首次可执行 open 尝试买入一次；没有 next open 的最终信号不成交。
逐 bar 净值保存 bar_return 和 valuation_time。风险/回撤取 UTC 每日最后估值并重算 daily_return，午夜估值归新日，不补无观测日。CAGR 用日快照的日历跨度。
ChanFxStrategy 返回不可交易目标，只输出结构；Forex/Futures 执行未定义，不能用 Equity 账户假装模拟。

## 运行与断点

```bash
conda activate quant-lab
python -m pytest -q
python scripts/verify_dataset.py --dataset-id <id>
python scripts/inspect_chan.py --dataset-id <id> --symbol EURUSD --plot
python -m pdb -c 'b src/chan/stroke.py:58' -c continue -m scripts.inspect_chan --dataset-id <id> --symbol EURUSD
```

直接脚本执行会加入项目根目录；`python -m scripts.xxx` 可从项目根目录运行。可选 editable 安装只发现 `src` 包，不创建新的源码层。
没有数据库、框架事件总线、GUI、Broker 或实时交易。
