# Quant Lab — Data Layer V2 Implementation Plan

## 0. 项目背景

当前 `quant-lab` 已经完成最小可审计回测链路：

```text
Yahoo Finance / yfinance
        ↓
spy_daily.parquet
        ↓
data_loader.py
        ↓
strategy.py
        ↓
execution.py
        ↓
portfolio.py
        ↓
backtest.py
        ↓
metrics / reports
```

当前版本主要用于：

- SPY
- 日线
- SMA20 / SMA60
- Long / Cash
- T 日 Close 生成信号
- T+1 Open 成交
- 整数股
- 固定手续费
- 固定滑点

现有工程已经具备以下重要能力：

- 下载与回测严格分离
- 冻结 Parquet 数据
- SHA-256 校验
- 下载 metadata
- 拒绝覆盖冻结数据
- 数据不自动排序、不自动补值、不自动修复
- OHLCV 数据质量检查
- Future Mutation Test
- 时间因果性测试
- Portfolio Accounting 测试
- Execution 测试
- Benchmark
- 可审计交易流水
- 可复现运行环境

这些能力必须保留。

本次开发不是推倒重写。

目标是在当前工程基础上，将数据层升级成一个可以长期支持：

```text
Yahoo
Tushare
未来的 AKShare / CCXT / Broker Data

↓

美股
A股
ETF
指数
多股票

↓

多因子
横截面 Ranking
LightGBM / ML

↓

Paper Trading
```

的数据基础设施。

---

# 1. 核心开发目标

实现 Data Layer V2。

最终数据链路：

```text
                         External Providers

                 ┌───────────┴───────────┐
                 ↓                       ↓
              Yahoo                   Tushare
                 ↓                       ↓
           YahooProvider          TushareProvider
                 │                       │
                 └──────────┬────────────┘
                            ↓
                    Immutable Source Data
                            ↓
                       Normalization
                            ↓
                    Canonical Schemas
                            ↓
                       Validation
                            ↓
        ┌───────────────────┼───────────────────┐
        ↓                   ↓                   ↓
       Bars             Adjustments       Reference Data
                                                │
                                                ├─ Instruments
                                                └─ Calendars
        └───────────────────┬───────────────────┘
                            ↓
                         DataStore
                            ↓
                          Loader
                            ↓
                 Research / Backtest / ML
```

必须满足：

1. Provider 与 Backtest 解耦。
2. Backtest 永远不主动访问互联网。
3. 支持 Yahoo 和 Tushare。
4. 数据统一成 Canonical Schema。
5. 明确区分：
   - Provider Source Data
   - Raw Price
   - Adjusted Price
6. 支持单标的和多标的数据读取。
7. 保留 dataset provenance。
8. 支持未来 A 股和 ML Ranking。
9. 保持现有 SPY 回测可复现。
10. 不为了架构引入无意义抽象。

---

# 2. 明确术语

本项目以后严格区分以下概念。

## 2.1 Source Data

指：

> 数据供应商实际返回的数据快照。

例如：

```text
Yahoo 返回的数据
Tushare 返回的数据
```

Source Data 只负责冻结和审计。

不要把 `source/raw` 与“未复权价格”混为一谈。

---

## 2.2 Raw Price

Raw Price 指：

> 历史交易时实际价格坐标中的未复权 OHLC。

例如：

```text
open_raw
high_raw
low_raw
close_raw
```

如果发生拆股：

```text
100
↓
1拆2
↓
50
```

Raw Price 保留：

```text
100 → 50
```

这种真实价格跳变。

---

## 2.3 Adjusted Price

Adjusted Price 指：

> 使用分红、拆股、送股等 Adjustment 信息处理后的研究价格。

主要用于：

- 收益率研究
- Momentum
- SMA
- 长期价格比较
- Feature Engineering

Adjusted Price 必须明确 adjustment semantics。

禁止出现一个叫：

```text
adjusted_price
```

但无法说明它到底如何复权的字段。

---

# 3. 当前 V1 Baseline

修改任何代码前必须保存并验证当前 baseline。

当前冻结 SPY 数据：

```text
data/raw/spy_daily.parquet
```

当前 SHA-256：

```text
bdd34d3bc950d433a5eeeaa594be558dd1c920dacbd61f8750366d8836bca19f
```

数据：

```text
symbol: SPY
rows: 2766
actual_start: 2015-01-02
actual_end: 2025-12-31
```

当前回测：

```text
strategy trade count: 45
strategy total return: 1.466718879583301
strategy CAGR: 0.08558235360852229

benchmark trade count: 1
benchmark total return: 2.9389675730204616
benchmark CAGR: 0.13278961489741126
```

当前报告文件 SHA：

```text
reports/trades.csv
1289681caaa855ee053a5e8e5d5b0eec3ce32b8653d949f91cdf6767663b0793

reports/equity.csv
d13a13076f5f9b92db9b2670e192cccc041c6ff57d0e3f6c08bc113bcb10edcf

reports/benchmark_trades.csv
fc9e05be8c9deec50498d006a41a41ada94f4653ab1ae597fc0d1a7ad94657cd

reports/benchmark_equity.csv
67a9a0bc28c036a1a2d9276b8659f173f193b34f98fb3ed8684845bbe698acd3
```

在修改前：

```bash
python -m pytest -q
python scripts/run_backtest.py
```

确认当前 baseline 正常。

本次重构完成后，必须保留一种 `legacy adjusted` 兼容模式，使上述历史 SPY 实验仍能复现。

不要为了新设计悄悄改变旧实验定义。

---

# 4. 本次明确不做什么

Data Layer V2 不负责：

- 实盘
- Paper Trading
- Broker API
- 做空
- 杠杆
- 分钟线
- Tick
- Order Book
- A股 T+1 成交限制
- A股涨跌停撮合
- ST 完整交易规则
- 停牌成交模拟
- 印花税完整模型
- 财务报表
- Fundamental Factor
- ML
- LightGBM
- 全 A 股批量下载
- Portfolio 多资产改造
- 参数优化
- Walk-Forward

这些是后续阶段。

本阶段只构建正确的数据基础设施。

---

# 5. 目标目录结构

将数据相关代码逐渐迁移为：

```text
quant-lab/
│
├── config/
│   ├── strategy.yaml
│   ├── backtest.yaml
│   └── data.yaml
│
├── data/
│   ├── source/
│   │   ├── yahoo/
│   │   └── tushare/
│   │
│   ├── normalized/
│   │   ├── bars/
│   │   │   ├── US/
│   │   │   │   └── 1d/
│   │   │   └── CN/
│   │   │       └── 1d/
│   │   │
│   │   ├── adjustments/
│   │   │   ├── US/
│   │   │   └── CN/
│   │   │
│   │   └── corporate_actions/
│   │       ├── US/
│   │       └── CN/
│   │
│   ├── reference/
│   │   ├── instruments/
│   │   └── calendars/
│   │
│   └── manifests/
│
├── src/
│   ├── data/
│   │   ├── __init__.py
│   │   ├── schema.py
│   │   ├── models.py
│   │   ├── normalize.py
│   │   ├── adjustment.py
│   │   ├── validation.py
│   │   ├── manifest.py
│   │   ├── store.py
│   │   ├── loader.py
│   │   │
│   │   └── providers/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── yahoo.py
│   │       └── tushare.py
│   │
│   ├── strategy.py
│   ├── execution.py
│   ├── portfolio.py
│   ├── backtest.py
│   ├── metrics.py
│   └── validation.py
│
├── scripts/
│   ├── download_data.py
│   ├── inspect_data.py
│   ├── verify_dataset.py
│   └── run_backtest.py
│
└── tests/
    ├── data/
    │   ├── test_schema.py
    │   ├── test_normalize.py
    │   ├── test_validation.py
    │   ├── test_adjustment.py
    │   ├── test_store.py
    │   ├── test_loader.py
    │   ├── test_yahoo_provider.py
    │   └── test_tushare_provider.py
    │
    ├── test_strategy.py
    ├── test_execution.py
    ├── test_accounting.py
    ├── test_backtest.py
    ├── test_metrics.py
    └── test_no_lookahead.py
```

现有：

```text
src/data_loader.py
```

可以在迁移期间作为 compatibility wrapper。

最终不能存在两份重复的数据读取实现。

---

# 6. Canonical Bar Schema

统一日线 Bar Schema。

Required：

```text
date
symbol

open
high
low
close
volume
```

Optional：

```text
amount
```

要求：

### date

```text
datetime64[ns]
timezone-naive
exchange session date
00:00:00
```

注意：

timezone-naive 不代表 UTC。

它表示：

> 对应交易所当地交易日标签。

例如：

```text
2026-01-05
```

表示当地交易所的 2026-01-05 交易 session。

---

### symbol

统一 provider canonical symbol。

例如：

```text
SPY
AAPL

000001.SZ
600519.SH
```

---

### OHLC

必须：

```text
finite
> 0
```

并满足：

```text
high >= max(open, close, low)

low <= min(open, close, high)
```

---

### volume

必须：

```text
finite
>= 0
integer-valued
```

不要因为 Provider 返回 float dtype 就默认它非法。

如果：

```text
1000.0
```

数学上是整数，可以 normalize 成整数。

但是：

```text
1000.5
```

必须报错。

---

# 7. 多标的数据格式

Loader 以后必须支持：

```python
symbols=["AAPL", "MSFT", "NVDA"]
```

返回 long-format：

```text
date        symbol   open   high   low   close   volume
2025-01-02  AAPL     ...
2025-01-02  MSFT     ...
2025-01-02  NVDA     ...
2025-01-03  AAPL     ...
```

不要设计：

```text
AAPL_close
MSFT_close
NVDA_close
```

这种 wide-format 作为内部 Canonical Storage。

原因：

未来 ML 数据天然是：

```text
date × symbol
```

结构。

---

# 8. Data Provider Interface

Provider 负责：

> 与外部供应商通信。

Provider 不负责：

- 回测
- Strategy
- Portfolio
- Metrics
- 自动保存实验
- 交易逻辑

定义一个简单 Provider Protocol 或 ABC。

不要建立复杂 Factory 体系。

目标接口：

```python
class DataProvider:
    name: str

    def fetch_bars(
        self,
        symbol: str,
        start: str,
        end: str,
        frequency: str = "1d",
    ):
        ...

    def fetch_instrument(self, symbol: str):
        ...

    def fetch_adjustments(
        self,
        symbol: str,
        start: str,
        end: str,
    ):
        ...

    def fetch_corporate_actions(
        self,
        symbol: str,
        start: str,
        end: str,
    ):
        ...

    def fetch_calendar(
        self,
        start: str,
        end: str,
    ):
        ...
```

不是每个 Provider 必须立刻完整实现全部 optional capability。

允许明确：

```python
raise NotImplementedError
```

但不能返回假的空数据掩盖“不支持”。

---

# 9. Provider Registry

统一入口使用简单 registry：

```python
PROVIDERS = {
    "yahoo": YahooProvider,
    "tushare": TushareProvider,
}
```

不要引入：

- Factory Pattern
- Dependency Injection Framework
- Plugin Framework
- IOC Container

没有必要。

---

# 10. YahooProvider

将当前 `scripts/download_data.py` 中 Yahoo-specific 代码迁移到：

```text
src/data/providers/yahoo.py
```

## 10.1 下载原则

新 Data Layer 不再把：

```text
auto_adjust=True
```

作为唯一源数据。

YahooProvider 应优先获取：

```text
unadjusted OHLC
volume
provider adjusted information
dividend
stock split
```

调用 Yahoo 时：

```text
auto_adjust=False
repair=False
```

公司行动应通过：

```text
actions=True
```

或者 Yahoo 明确的 action 接口获取。

禁止：

```text
repair=True
```

静默修改数据。

如果未来希望使用 repair：

必须成为单独、显式的 experiment option。

---

# 11. Yahoo 日期处理

保留当前正确逻辑：

> 先转换成 exchange timezone，再移除 timezone。

禁止：

```text
先转UTC
↓
再去timezone
```

造成 session date 变化。

YahooProvider 负责把供应商 timestamp 转换成：

```text
timezone-naive exchange session date
```

Normalizer 之后的数据不能再包含 timezone。

Yahoo 的 provider-specific timezone 逻辑只能存在于 YahooProvider。

禁止 `src/data/validation.py` 中出现：

```text
America/New_York
SPY
Yahoo
```

等 provider-specific 逻辑。

---

# 12. TushareProvider

新增：

```text
src/data/providers/tushare.py
```

依赖：

```text
tushare
```

Token 从环境变量读取：

```text
TUSHARE_TOKEN
```

禁止：

- 把 token 写进代码
- 把 token 写进 YAML
- 把 token commit 到 Git

如果没有 token：

明确失败：

```text
TUSHARE_TOKEN is not configured
```

---

# 13. Tushare A股行情

Canonical Source 优先使用：

```text
未复权行情
```

而不是直接把：

```text
qfq
```

保存成唯一数据。

建议：

```text
Tushare daily raw price
+
adj_factor
```

独立保存。

不要将动态前复权结果作为唯一事实源。

---

# 14. Tushare Adjustment

保存：

```text
date
symbol
adj_factor
provider
factor_semantics
```

Tushare 的 qfq / hfq 由 Adjustment Layer 生成。

禁止 Strategy 直接调用：

```python
ts.pro_bar(..., adj="qfq")
```

作为正式研究的数据入口。

可以在测试中使用 Tushare `qfq/hfq` 结果验证我们自己的 Adjustment 结果。

---

# 15. Adjustment Layer

建立：

```text
src/data/adjustment.py
```

职责：

```text
Raw OHLC
+
Adjustment Factor
↓
Adjusted OHLC
```

明确支持不同 price basis：

```text
raw
provider_adjusted
qfq
hfq
```

不要默认某一个就是正确答案。

API 可以类似：

```python
adjust_bars(
    bars,
    adjustments,
    method="qfq",
)
```

---

# 16. Adjustment 的重要规则

不能假设：

```text
Yahoo factor
==
Tushare factor
```

不同 Provider 的 factor scale 可以不同。

因此 adjustment dataset 必须保存：

```text
provider
factor_semantics
```

例如：

```text
provider = tushare
factor_semantics = cumulative_adjustment_factor
```

Yahoo：

```text
provider = yahoo
factor_semantics = provider_adjusted_close_ratio
```

禁止把它们当成同一个绝对数值含义。

---

# 17. 当前 V1 Adjusted SPY 兼容

当前 V1 使用：

```text
Yahoo auto_adjust=True OHLC
```

进行：

- Signal
- Execution
- Valuation

它是 synthetic adjusted-price account。

本次升级不能偷偷把现有回测变成：

```text
raw price execution
```

因为这会改变实验定义。

Data Layer V2 应提供：

```text
legacy_provider_adjusted
```

兼容路径。

当前 SPY regression test 必须继续通过。

未来真正执行：

```text
Raw Price
+
Corporate Actions
+
真实 Share Quantity
```

属于下一阶段。

---

# 18. Corporate Action Schema

建立基础结构：

```text
date
symbol
action_type
cash_amount
split_ratio
provider
```

`action_type` 初步支持：

```text
dividend
split
```

不要在 Data Layer V2 中实现：

```text
Portfolio 自动收股息
拆股自动修改 quantity
```

这里只负责正确保存数据。

---

# 19. Instrument Reference Data

建立：

```text
data/reference/instruments/
```

Canonical Instrument Schema：

```text
symbol
name
market
exchange
asset_type
currency
list_date
delist_date
provider
```

允许部分字段未知。

但：

```text
symbol
market
asset_type
```

应该尽可能明确。

示例：

```text
SPY
SPDR S&P 500 ETF Trust
US
NYSE_ARCA
ETF
USD

600519.SH
贵州茅台
CN
SSE
EQUITY
CNY
```

---

# 20. Trading Calendar

建立 Canonical Calendar：

```text
market
date
is_open
provider
```

TushareProvider 使用交易日历接口。

US 市场如果暂时没有正式 calendar source：

保留：

```text
weekday check
```

作为最低检查，

但必须在 manifest / assumptions 明确写：

```text
Exact exchange holiday completeness is not independently verified.
```

禁止把：

```text
weekday < 5
```

描述成完整交易日历。

---

# 21. Validation 重构

当前：

```text
src/validation.py
```

同时承担：

- Market Data Validation
- Future Mutation Test

拆分：

```text
src/data/validation.py
```

负责数据质量。

原：

```text
src/validation.py
```

保留：

- future_mutation_test
- strategy causality validation
- research validation

---

# 22. Common Data Validation

实现：

```python
validate_bars()
```

检查：

```text
nonempty

required columns

datetime type

timezone-naive

normalized date

date + symbol 唯一

按 symbol/date 正确排序

OHLC numeric

finite

OHLC > 0

volume >= 0

volume integer-valued

high relationship

low relationship
```

禁止：

```text
自动排序
自动 drop_duplicates
自动 fillna
自动修改 high/low
自动 repair
```

错误必须明确抛异常。

---

# 23. Market-specific Validation

另外允许：

```python
validate_us_daily_bars(...)
validate_cn_daily_bars(...)
```

但不要建立复杂 class inheritance。

US 初期检查：

```text
没有 weekend session
```

CN 初期检查：

```text
没有 weekend session
如果存在 calendar：
必须是合法 open date
```

未来：

```text
涨跌停
ST
停牌
```

属于 execution/data enrichment 阶段，不在当前实现。

---

# 24. DataStore

建立：

```text
src/data/store.py
```

Store 只负责：

```text
save
load
locate
checksum
```

禁止 Store：

```text
本地没有数据
↓
自动联网下载
```

必须坚持：

```text
Download 是显式行为。
Backtest 是纯本地行为。
```

---

# 25. Normalized Storage

建议：

```text
data/normalized/bars/US/1d/SPY.parquet
data/normalized/bars/US/1d/AAPL.parquet

data/normalized/bars/CN/1d/000001.SZ.parquet
data/normalized/bars/CN/1d/600519.SH.parquet
```

调整数据：

```text
data/normalized/adjustments/US/SPY.parquet
data/normalized/adjustments/CN/000001.SZ.parquet
```

Corporate Actions：

```text
data/normalized/corporate_actions/US/SPY.parquet
```

---

# 26. Source Data Storage

Provider 原始快照：

```text
data/source/yahoo/
data/source/tushare/
```

Source 数据：

- 不覆盖
- 不静默修改
- 不作为 Backtest 直接输入
- 用于审计和重新 normalize

如果相同请求重新下载结果不同：

生成新 dataset version。

不要覆盖旧版本。

---

# 27. Dataset Manifest

将当前 metadata 升级为 manifest。

至少包含：

```json
{
  "schema_version": 2,
  "dataset_id": "...",

  "provider": "yahoo",
  "provider_version": "...",

  "market": "US",
  "asset_type": "ETF",
  "symbols": ["SPY"],
  "frequency": "1d",

  "requested_start": "2015-01-01",
  "requested_end_inclusive": "2025-12-31",

  "actual_start": "2015-01-02",
  "actual_end": "2025-12-31",

  "price_data": {
    "raw_ohlc": true,
    "adjustment_available": true,
    "provider_adjusted_available": true
  },

  "rows": 2766,

  "date_semantics": "timezone-naive exchange session date",

  "downloaded_at_utc": "...",

  "source_sha256": "...",
  "normalized_sha256": "...",

  "normalizer_version": 2,

  "assumptions": []
}
```

必须：

```text
allow_nan=False
```

Manifest 本身也应该可校验。

---

# 28. dataset_id

实现稳定可读的 dataset ID。

不需要复杂 UUID 系统。

可以由：

```text
provider
market
symbol
frequency
start
end
download timestamp
```

生成。

例如：

```text
yahoo_US_SPY_1d_20150101_20251231_20261004T...
```

或者使用内容 hash。

核心要求：

> 不同冻结版本可以被唯一识别。

---

# 29. Loader API

建立：

```text
src/data/loader.py
```

目标：

```python
load_bars(
    market="US",
    symbols=["SPY"],
    start="2015-01-01",
    end="2025-12-31",
    frequency="1d",
    price_basis="legacy_provider_adjusted",
)
```

多股票：

```python
load_bars(
    market="US",
    symbols=["AAPL", "MSFT", "NVDA"],
    start="2020-01-01",
    end="2025-12-31",
    frequency="1d",
    price_basis="raw",
)
```

返回 long-format。

---

# 30. Loader 必须做什么

Loader：

```text
定位本地数据
验证 Manifest
验证 SHA
读取 Parquet
按请求日期筛选
按 symbols 筛选
调用 validate_bars
返回数据
```

Loader 不能：

```text
联网
自动下载
自动补数据
自动修复
```

---

# 31. Legacy Compatibility

当前：

```python
load_market_data(path, start_date, end_date)
```

可以暂时保留。

内部改成调用新 Loader。

不要保留两套读取逻辑。

例如：

```python
def load_market_data(...):
    return ...
```

只作为 compatibility wrapper。

---

# 32. Backtest 去除 SPY Hardcode

当前：

```python
if symbol != 'SPY':
    raise ValueError('This phase supports SPY only')
```

删除。

Backtest 应该只关心：

```text
symbol
bars
strategy
costs
```

而不关心：

```text
Yahoo
Tushare
SPY
New York
```

---

# 33. Backtest 当前仍保持单资产

Data Loader 可以支持多 symbol。

但本阶段 `run_backtest()` 可以仍然要求：

```text
exactly one symbol
```

如果传入多 symbol：

明确失败：

```text
Current backtest engine supports one symbol; Data Layer supports multi-symbol datasets.
```

不要在 Data Layer V2 顺便重写 Multi-Asset Portfolio。

---

# 34. run_backtest.py 解耦 Provider

当前存在：

```text
auto_adjust == True
SPY
New York
```

hardcode。

必须删除。

`run_backtest.py` 不再知道：

```text
Yahoo
yfinance
auto_adjust
```

它只检查：

```text
dataset manifest
price_basis
symbol
checksum
```

---

# 35. Report 文案通用化

当前：

```text
SPY SMA 20/60
SPY buy & hold
New York session date
adjusted OHLC
```

改成动态：

```text
{symbol} SMA {fast}/{slow}

{symbol} buy & hold
```

X Axis：

```text
Exchange session date
```

Report audit 中必须记录：

```text
market
provider
price_basis
dataset_id
manifest
```

---

# 36. data.yaml

新增：

```yaml
storage:
  source_dir: data/source
  normalized_dir: data/normalized
  reference_dir: data/reference
  manifest_dir: data/manifests

defaults:
  frequency: 1d

providers:
  yahoo:
    enabled: true

  tushare:
    enabled: true
    token_env: TUSHARE_TOKEN
```

不得在文件里保存真实 token。

---

# 37. strategy.yaml

可以扩展：

```yaml
symbol: SPY
market: US

fast_window: 20
slow_window: 60

price_basis: legacy_provider_adjusted
```

后面新实验：

```yaml
symbol: AAPL
market: US

fast_window: 20
slow_window: 60

price_basis: raw
```

注意：

当前 V1 SPY 为保持 regression：

```text
legacy_provider_adjusted
```

---

# 38. backtest.yaml

逐渐移除：

```text
data_path
```

改成 DataStore 解析。

保留：

```text
initial_cash
commission_rate
slippage_rate

start_date
end_date

reports_dir

annualization_factor
risk_free_rate
```

数据位置属于 Data Layer。

不应该由 Backtest Config 直接硬编码某一个 Parquet 路径。

---

# 39. 统一 Download CLI

保留：

```text
scripts/download_data.py
```

但改成 provider-neutral。

示例：

```bash
python scripts/download_data.py --provider yahoo --market US --symbol SPY --start 2015-01-01 --end 2025-12-31 --frequency 1d
```

A股：

```bash
python scripts/download_data.py --provider tushare --market CN --symbol 000001.SZ --start 2015-01-01 --end 2025-12-31 --frequency 1d
```

参数定义：

```text
--provider
data provider

--market
market identifier

--symbol
instrument symbol

--start
inclusive start date

--end
inclusive end date

--frequency
bar frequency
```

CLI 负责：

```text
解析参数
↓
选择 Provider
↓
fetch
↓
保存 source snapshot
↓
normalize
↓
validate
↓
保存 normalized
↓
生成 manifest
```

---

# 40. inspect_data.py

新增：

```text
scripts/inspect_data.py
```

用于快速查看：

```text
dataset_id
provider
symbol
market
date range
rows
price basis
missing values
duplicate keys
first rows
last rows
SHA
```

它只读取本地。

不联网。

---

# 41. verify_dataset.py

新增：

```text
scripts/verify_dataset.py
```

功能：

```text
读取 Manifest
↓
验证文件存在
↓
重新计算 SHA
↓
运行 schema validation
↓
运行 bar validation
↓
输出 PASS / FAIL
```

用于独立检查冻结数据。

---

# 42. Yahoo 测试样本

Data Layer V2 完成后至少验证：

```text
SPY
AAPL
```

原因：

SPY 保证旧逻辑兼容。

AAPL 验证系统已经去掉：

```text
SPY-only
```

hardcode。

---

# 43. Tushare 测试样本

至少验证：

```text
000001.SZ
600519.SH
```

暂时不下载全 A 股。

验证：

```text
Tushare
↓
Provider
↓
Source
↓
Normalize
↓
Validate
↓
Store
↓
Load
```

完整链路。

---

# 44. Unit Tests — Schema

新增：

```text
tests/data/test_schema.py
```

验证：

- required columns
- dtype
- date semantics
- symbol
- invalid schemas fail

---

# 45. Unit Tests — Validation

新增：

```text
tests/data/test_validation.py
```

至少覆盖：

```text
duplicate date/symbol

unsorted

NaN

Infinity

zero price

negative price

impossible high

impossible low

negative volume

fractional volume

timezone-aware date

time-of-day

weekend
```

保留当前：

> never silently repair

原则。

---

# 46. Provider Tests

Provider Unit Test：

禁止依赖真实网络。

使用 monkeypatch / fixture 模拟 Provider Response。

Yahoo：

测试：

```text
inclusive end handling
timezone handling
auto_adjust=False
repair=False
actions
source normalization
```

Tushare：

测试：

```text
trade_date parsing
reverse chronological provider output
column rename
vol → volume
symbol
token absence
```

注意：

如果 Provider 默认返回日期倒序：

Normalizer 可以显式 sort，

但是：

> 这个 sort 属于 Provider → Canonical 的确定性 normalization。

与 Loader 在发现脏数据后“偷偷修复”不是一回事。

必须在代码中明确区分这两个阶段。

---

# 47. Adjustment Tests

手工构造拆股。

例如：

```text
Day 1 raw close = 100
Day 2 split 2:1
Day 2 raw close = 50
```

验证 adjusted series 连续。

再构造现金分红。

验证：

```text
Raw
Adjusted
```

含义正确。

---

# 48. Tushare Adjustment Verification

对于固定测试区间：

使用：

```text
raw + adj_factor
```

自行生成：

```text
qfq
hfq
```

然后与 Tushare 提供的：

```text
pro_bar(adj="qfq")
pro_bar(adj="hfq")
```

进行数值比较。

允许合理浮点 tolerance。

如果结果不一致：

不要调整测试去适配。

先找公式或数据语义问题。

---

# 49. Store Tests

测试：

```text
save
↓
sha
↓
load
```

结果一致。

冻结文件：

```text
默认拒绝 overwrite
```

已有 dataset 不允许无提示覆盖。

---

# 50. Manifest Tests

测试：

```text
manifest schema
sha mismatch
missing file
wrong symbol
wrong provider
wrong date range
```

必须失败。

---

# 51. Multi-symbol Loader Test

使用人工数据：

```text
AAPL
MSFT
```

测试：

```python
load_bars(symbols=["AAPL", "MSFT"])
```

返回：

```text
date + symbol
```

唯一、升序、数据完整。

---

# 52. Existing Tests

以下已有测试必须保留：

```text
test_future_mutation

test_future_prices_do_not_change_past_accounts

test_tomorrow_close_does_not_decide_tomorrow_open

test_accounts_reconcile_every_day

test_parquet_loader_and_no_silent_repair

test_adjusted_download_inclusive_end_and_frozen_file
```

允许因为模块路径变化修改 import。

禁止删除测试能力。

---

# 53. Regression Test

新增一个：

```text
test_legacy_spy_regression.py
```

加载现有 frozen：

```text
data/raw/spy_daily.parquet
```

运行 legacy 模式。

至少断言：

```text
data rows = 2766

first date = 2015-01-02

last date = 2025-12-31

trade count = 45
```

关键指标与当前 baseline 一致。

合理使用：

```text
pytest.approx
```

处理浮点。

---

# 54. New Generic Backtest Test

使用：

```text
AAPL fixture
```

确保：

```text
run_backtest(..., symbol="AAPL")
```

不会因为：

```text
symbol != SPY
```

失败。

---

# 55. Dependencies

保留现有：

```text
pandas
numpy
pyarrow
PyYAML
matplotlib
pytest
yfinance
```

新增：

```text
tushare
```

不要因为本阶段任务安装：

```text
polars
duckdb
sqlalchemy
vectorbt
qlib
backtrader
```

除非有明确、不可替代的必要性。

---

# 56. requirements-lock

修改：

```text
requirements.txt
```

之后更新：

```text
requirements-lock.txt
```

锁定本次实际测试环境。

不要手写假的 lock 版本。

---

# 57. Security

`.gitignore` 必须确保不提交：

```text
.env
credentials
tokens
API keys
provider cache
downloaded market datasets
reports
```

新增：

```text
.env.example
```

可以只写：

```text
TUSHARE_TOKEN=
```

但程序不要求自动解析 `.env`。

优先读取真实系统环境变量。

避免为了 `.env` 引入额外依赖。

---

# 58. AGENTS.md 更新

更新 Data 部分。

明确：

```text
Data Provider
↓
Source Snapshot
↓
Normalization
↓
Validation
↓
Frozen Store
↓
Backtest
```

并明确：

- Backtest 不联网
- Provider 不进入 Strategy
- Raw Price 和 Source Data 不是同一个概念
- Adjustment semantics 必须显式
- 禁止静默修复
- 数据版本必须可审计

同时将：

```text
Current phase = SPY only
```

更新成：

> Data Layer 支持多市场，但 Backtest Engine 仍是单资产 Long/Cash。

---

# 59. README 更新

README 增加：

## Data Architecture

解释：

```text
Provider
Source
Normalized
Manifest
Store
Loader
```

## Price Semantics

解释：

```text
raw
provider_adjusted
qfq
hfq
legacy_provider_adjusted
```

## Yahoo Example

## Tushare Example

## Dataset Verification

## Known Limitations

---

# 60. Current README 中必须更新的地方

当前：

```text
仅用于 SPY 日线研究
```

应该改成：

> 当前交易引擎仍为单资产日线研究，但数据层开始支持 US/CN 多标的数据管理。

不要声称：

```text
系统已经支持全市场多资产回测
```

因为 Portfolio 还没有升级。

---

# 61. 开发阶段顺序

不要一次性写完然后最后运行测试。

按以下 Phase 开发。

---

## Phase 0 — Baseline

完成：

```text
run pytest

run current SPY backtest

record baseline
```

如果当前 baseline 就失败：

先停止重构并定位。

---

## Phase 1 — Schema / Validation / Store

实现：

```text
schema
validation
manifest
store
```

此阶段不接 Provider。

用人工 fixture 完成测试。

---

## Phase 2 — YahooProvider

把现有 Yahoo 下载逻辑迁入：

```text
YahooProvider
```

实现：

```text
raw/unadjusted source
actions
metadata
timezone
normalization
```

保持旧 SPY regression。

---

## Phase 3 — Loader

实现：

```text
single symbol
multi-symbol

date range
price basis
checksum
```

将旧：

```text
load_market_data()
```

改为 compatibility wrapper。

---

## Phase 4 — Backtest Decoupling

移除：

```text
SPY-only
Yahoo-only
New York-only
auto_adjust-only
```

hardcode。

保持 Backtest 单资产。

---

## Phase 5 — TushareProvider

实现：

```text
raw daily bars
adj_factor
instrument
calendar
```

Token 使用环境变量。

---

## Phase 6 — Adjustment Layer

实现：

```text
raw
qfq
hfq
provider_adjusted
```

增加 adjustment tests。

---

## Phase 7 — CLI

升级：

```text
download_data.py
inspect_data.py
verify_dataset.py
run_backtest.py
```

---

## Phase 8 — Documentation / Regression

更新：

```text
AGENTS.md
README.md
config
requirements
```

运行完整测试。

---

# 62. 每个 Phase 完成后的规则

每个 Phase 都必须：

```bash
python -m pytest -q
```

相关测试通过后才能继续下一阶段。

如果测试失败：

优先修改实现。

禁止为了通过测试：

```text
删除测试
降低断言
修改 expected value 迎合错误实现
```

除非能够明确证明旧测试本身错误。

这种情况必须解释原因。

---

# 63. End-to-End 验收

最终至少完成以下四个数据集验证：

```text
Yahoo / SPY
Yahoo / AAPL

Tushare / 000001.SZ
Tushare / 600519.SH
```

Yahoo：

```text
下载
↓
冻结
↓
normalize
↓
manifest
↓
verify
↓
load
```

Tushare 同样。

---

# 64. SPY Legacy 验收

现有 frozen SPY 数据必须：

```text
继续可加载
继续可回测
future mutation pass
account reconciliation pass
```

Legacy regression：

```text
45 strategy fills
1 benchmark fill
```

不得因为 Data Layer 重构变化。

---

# 65. AAPL 验收

AAPL 的目标不是检查策略盈利。

只检查：

```text
symbol 通用化成功
Yahoo Provider 通用
数据质量正常
Backtest 不再 SPY-only
```

SMA 回测可以正常结束即可。

---

# 66. A股验收

对于：

```text
000001.SZ
600519.SH
```

本阶段的 SMA Backtest 只作为：

> Data Pipeline Smoke Test。

必须在 report 中标记：

```text
This backtest does not yet model all China A-share market-specific execution rules.
```

不要把结果解释成真实可交易绩效。

---

# 67. Error Handling

以下情况必须 fail loudly：

```text
provider 返回空数据

日期错误

缺 token

checksum mismatch

schema mismatch

unknown provider

unknown price basis

duplicate bars

missing required columns

corrupt parquet

manifest mismatch
```

禁止：

```text
打印 warning
然后偷偷继续
```

对于会影响实验正确性的错误，直接异常。

---

# 68. Logging

暂时不需要引入 logging framework。

可以使用：

```python
print()
```

输出 CLI 状态。

但是信息必须清楚：

```text
Provider
Symbol
Requested Range
Actual Range
Source Path
Normalized Path
Manifest
SHA
Rows
```

不要输出 API Token。

---

# 69. Coding Style

遵守现有 AGENTS.md。

特别强调：

```text
简单
显式
可审计
```

禁止过度设计。

不要引入：

```text
BaseManager
DataService
Repository
ProviderFactoryFactory
Singleton
Dependency Injection
```

如果一个简单 dict 可以解决，就使用 dict。

如果函数就能表达，不要为了“OOP”强制使用 class。

Provider 使用 class 是因为它有明确外部数据源职责。

---

# 70. 最终代码原则

最终必须形成清晰边界：

```text
Provider
= 怎么从外面拿数据

Normalizer
= 怎么变成内部格式

Adjustment
= 怎么构造不同价格坐标

Validator
= 数据是否合法

Store
= 数据保存在哪里

Manifest
= 数据从哪里来、是什么版本

Loader
= Research 怎么读取

Strategy
= 根本不知道 Yahoo/Tushare

Backtest
= 根本不知道 Yahoo/Tushare
```

---

# 71. 最终成功标准

只有全部满足以下条件才算完成 Data Layer V2：

- 所有 pytest 通过
- 旧 SPY regression 通过
- SPY 不再是 Data Layer hardcode
- AAPL 可以走完整 Yahoo pipeline
- Tushare Provider 可用
- 000001.SZ 可以走完整 pipeline
- 600519.SH 可以走完整 pipeline
- Provider 与 Backtest 解耦
- Provider 与 Strategy 解耦
- Source Data 可审计
- Normalized Data 有统一 schema
- Manifest 有 SHA
- Raw / Adjusted 语义明确
- Loader 支持多 symbol
- Backtest 仍保持单 symbol，并明确限制
- Backtest 永不联网
- Tushare Token 不进入 Git
- README / AGENTS 与代码一致
- 不存在静默数据修复
- future mutation tests 仍通过
- account reconciliation tests 仍通过

---

# 72. 完成后不要继续做

Data Layer V2 完成以后：

不要自行继续实现：

```text
Multi-Asset Portfolio
Top-K
LightGBM
A股真实撮合
Paper Trading
VectorBT
Walk-Forward
```

先停止。

等待对 Data Layer V2 做一次人工 review。

---

# 73. 最终向我汇报

完成后请提供：

## Architecture

最终目录结构。

## Changed Files

新增、修改、删除了哪些文件。

## Dependencies

新增了哪些依赖以及原因。

## Tests

```text
pytest passed / total
```

以及新增测试列表。

## Legacy Regression

报告：

```text
SPY dataset hash
rows
date range
trade count
total return
CAGR
```

是否与原 baseline 一致。

## Yahoo Verification

报告：

```text
SPY
AAPL
```

的数据范围、行数、manifest、SHA。

## Tushare Verification

报告：

```text
000001.SZ
600519.SH
```

的数据范围、行数、manifest、SHA。

## Price Semantics

明确说明当前系统中的：

```text
raw
provider_adjusted
qfq
hfq
legacy_provider_adjusted
```

分别如何产生。

## Known Limitations

列出仍然存在的：

- Yahoo 数据质量限制
- Tushare 权限限制
- Trading Calendar 限制
- Corporate Action 限制
- A 股 Execution 限制
- 当前 Backtest 单资产限制

## Next Recommended Step

只提出下一阶段建议。

不要自行实施下一阶段。

---

# 74. 最重要的原则

Data Layer V2 的目标不是：

> 让目录看起来像大型交易平台。

目标是：

> 建立一个可以可靠回答“这份数据从哪里来、经过了什么处理、使用的到底是什么价格、能不能复现”的研究数据基础设施。

如果一个抽象不能提高：

```text
正确性
可复现性
可审计性
多数据源兼容性
```

就不要引入。

如果一个简单实现已经能够明确表达数据语义，就优先选择简单实现。
