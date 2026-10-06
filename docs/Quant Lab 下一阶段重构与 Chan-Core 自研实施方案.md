# Quant Lab 下一阶段重构与 Chan-Core 自研实施方案

## 0. 任务背景

当前项目：

https://github.com/aqwddda/quant-lab/tree/dev

当前开发分支为：

```text
dev
```

````

请首先完整阅读当前 `dev` 分支代码、README、tests 和 Data Layer V2 的设计文档，再开始修改。

参考的缠论工程：

https://github.com/Vespa314/chan.py

重点参考以下代码的**工程设计思想**：

```text
Combiner/KLine_Combiner.py

KLine/KLine.py
KLine/KLine_List.py
KLine/KLine_Unit.py

Bi/Bi.py
Bi/BiList.py
Bi/BiConfig.py
```

注意：

**不要直接复制 Vespa314/chan.py 的缠论规则。**

我们自己的 Chan-Core 必须按照本项目已经确认的规则实现。

Vespa 项目主要用于学习：

- 增量状态更新
- 数据对象与状态管理器分离
- K 线合并器设计
- 笔对象与笔列表/状态机分离
- confirmed / virtual / tentative 状态设计
- 模块间边界
- 多层结构向上扩展的方法

不要为了“和 Vespa 一致”修改我们的业务规则。

---

# 1. 总体目标

本次不是单纯增加一个缠论算法文件。

目标是把 Quant Lab 从当前：

```text
US/CN
+
Daily Bar
+
SMA Strategy
+
Long-only Equity Backtest
```

演进为：

```text
通用 Market Data
        ↓
多资产 / 多周期
        ↓
Market Structure Engine
        ↓
Strategy
        ↓
Backtest Engine
        ↓
Execution / Portfolio
```

并实现第一版自研：

```text
chan-core
```

第一阶段 Chan-Core 只实现：

```text
K线包含处理
    ↓
处理后K线
    ↓
顶/底分型
    ↓
笔
```

暂时不要实现：

```text
线段
中枢
背驰
一二三买卖点
多级别联立
完整朋友交易策略
```

除非当前仓库已有明确规则，否则不要自行补全缠论理论。

---

# 2. 最重要的架构原则

最终依赖方向必须保持：

```text
Provider
    ↓
Data Layer
    ↓
Canonical Bars
    ↓
Market Structure / Features
    ↓
Strategy
    ↓
Orders
    ↓
Execution
    ↓
Portfolio
    ↓
Metrics
```

必须满足：

```text
Data Layer 不知道 Chan

Chan-Core 不知道 Yahoo / Tushare / MT5 / OANDA

Chan-Core 不知道 Strategy

Strategy 不知道数据来自哪个 Provider

Backtest Engine 不知道 Strategy 是 SMA、Chan 还是 ML

Metrics 不依赖具体 Strategy
```

禁止出现类似：

```python
if strategy == "chan":
    ...
```

写进 Data Layer 或 Backtest Engine。

也禁止：

```python
if market == "FX":
    ...
elif market == "US":
    ...
```

在通用核心逻辑里不断堆条件分支。

资产差异应该通过明确的数据模型、Provider、Validator、Execution Model 表达。

---

# 3. 不允许破坏当前实验

当前 `dev` 分支已有一套冻结数据、SHA、Manifest、V1 compatibility 和 SPY regression。

这些必须保留。

重构完成后：

```bash
python -m pytest -q
```

现有测试必须全部通过。

特别是当前冻结 SPY 实验必须保持历史结果完全一致。

不要重新下载 SPY 数据替代历史冻结数据。

不要修改旧 Manifest。

不要修改旧数据文件。

不要为了新架构重新生成旧实验结果。

采用：

```text
Backward Compatibility
```

而不是：

```text
破坏 V2 → 全部迁移数据
```

---

# 4. Python 工程结构重构

当前项目已经开始明显超过单层 `src/*.py` 的规模。

请迁移为标准 `src layout`。

目标结构：

```text
quant-lab/
│
├── pyproject.toml
├── README.md
├── AGENTS.md
│
├── config/
├── docs/
├── scripts/
├── tests/
│
└── src/
    └── quant_lab/
        │
        ├── __init__.py
        │
        ├── market/
        │   ├── __init__.py
        │   ├── enums.py
        │   ├── timeframe.py
        │   └── models.py
        │
        ├── data/
        │   ├── __init__.py
        │   ├── schema.py
        │   ├── models.py
        │   ├── manifest.py
        │   ├── validation.py
        │   ├── loader.py
        │   ├── store.py
        │   ├── adjustment.py
        │   ├── resample.py
        │   │
        │   ├── normalization/
        │   │   ├── __init__.py
        │   │   ├── yahoo.py
        │   │   ├── tushare.py
        │   │   └── local.py
        │   │
        │   └── providers/
        │       ├── __init__.py
        │       ├── base.py
        │       ├── yahoo.py
        │       ├── tushare.py
        │       └── local.py
        │
        ├── chan/
        │   ├── __init__.py
        │   ├── config.py
        │   ├── enums.py
        │   ├── models.py
        │   ├── combiner.py
        │   ├── fractal.py
        │   ├── stroke.py
        │   └── analyzer.py
        │
        ├── strategies/
        │   ├── __init__.py
        │   ├── base.py
        │   ├── sma.py
        │   └── chan_fx.py
        │
        └── backtest/
            ├── __init__.py
            ├── models.py
            ├── engine.py
            ├── execution.py
            ├── portfolio.py
            └── metrics.py
```

不要为了“架构漂亮”继续细分几十个文件。

保持：

```text
一个模块一个明确职责
```

即可。

---

# 5. 增加 pyproject.toml

项目改为可编辑安装：

```bash
python -m pip install -e .
```

之后代码统一：

```python
from quant_lab.data.loader import ...
from quant_lab.chan import ChanAnalyzer
from quant_lab.backtest.engine import ...
```

不再依赖：

```python
sys.path.insert(...)
```

也不要继续使用：

```python
from src.xxx import ...
```

旧入口如有必要可以暂时保留 compatibility wrapper。

---

# 6. Market Domain Model

增加：

```text
quant_lab/market/
```

这里放跨 Data / Chan / Strategy / Backtest 共用的最基础市场对象。

至少包括：

```python
AssetClass

EQUITY
FOREX
FUTURES
```

以后可以扩：

```text
CRYPTO
OPTION
```

但现在不要实现不需要的逻辑。

增加 `Timeframe`。

至少支持：

```text
1m
5m
15m
30m
1h
4h
1d
```

不要在业务代码到处直接比较字符串。

应该有一个统一对象或 Enum / Value Object，可以完成：

```text
parse
validate
排序
是否可以 resample
转换为 duration
```

例如：

```python
Timeframe.parse("15m")
```

---

# 7. Canonical Bar V3

现有 V2 使用：

```text
date
symbol
open
high
low
close
volume
```

并且 `date` 是 timezone-naive session date。

这无法正确表达分钟、小时和 Forex。

增加新的 Canonical Bar V3。

核心字段：

```text
timestamp
symbol
open
high
low
close
```

可选字段：

```text
volume
tick_volume
amount
open_interest
```

原则：

```text
OHLC 是必需字段

volume 不应该成为所有资产的强制字段

Forex 可以没有真实 volume

Forex 可以有 tick_volume

Futures 可以有 open_interest
```

`timestamp` 必须是：

```text
timezone-aware UTC timestamp
```

不要使用 timezone-naive intraday timestamp。

Manifest 中必须明确：

```text
timeframe

timestamp_semantics

source_timezone

session_timezone / aggregation_timezone（如适用）
```

第一版统一推荐：

```text
timestamp_semantics = bar_start
```

对于 Provider 原始数据不是 bar start 的情况，Normalization 必须显式转换，并在 assumptions 中记录。

---

# 8. 不要删除 V2 Schema

不要强行把已有 V2 frozen data 改成 V3。

应该：

```text
Schema V1 / V2
    ↓
Compatibility Reader

Schema V3
    ↓
新的通用 Market Data API
```

已有 Manifest schema version 继续可读。

新 Dataset 使用新的：

```text
schema_version = 3
```

旧数据：

```text
不改
不覆盖
不重新生成
```

---

# 9. Asset / Venue 模型

不要再把：

```text
market = US
market = CN
```

作为唯一最高级别市场定义。

V3 至少区分：

```text
asset_class
venue
symbol
provider
```

例如：

```text
AAPL

asset_class = equity
venue = NASDAQ
provider = yahoo
```

Forex：

```text
EURUSD

asset_class = forex
venue = 某 broker/feed
provider = xxx
```

Futures：

```text
ESZ26

asset_class = futures
venue = CME
provider = xxx
```

Instrument metadata 中预留：

```text
symbol
provider_symbol

asset_class
venue

base_currency
quote_currency

tick_size
lot_size

contract_multiplier
expiry
```

字段可以 nullable，但 schema 要能够表达。

Forex 很重要：

```text
内部 canonical symbol
```

和：

```text
provider symbol
```

必须分开。

例如：

```text
EURUSD
EURUSD.a
EURUSDm
```

内部都可以映射成：

```text
EURUSD
```

但必须保存原始 provider_symbol。

---

# 10. Data Provider 设计

当前 Provider 思想保留：

```text
外部 API 通信
↓
原始响应
↓
Source Snapshot
```

Provider 不负责：

```text
策略
复权策略选择
回测
Chan
```

Provider 只负责：

```text
获取数据
保存原始 provider semantics
```

调整 base protocol。

不要再在 base provider 中硬编码：

```python
frequency == "1d"
```

Provider 应该声明 capability。

例如概念上：

```python
class ProviderCapabilities:
    asset_classes
    timeframes
    supports_adjustments
    supports_corporate_actions
    supports_calendar
```

不要设计复杂插件框架。

简单、明确即可。

---

# 11. 先不要猜 Forex 网络 Provider

当前我们还没有最终确定朋友使用：

```text
MT5 哪个 broker
OANDA
Dukascopy
其他 feed
```

因此本次不要擅自引入新的线上 API。

先实现：

```text
LocalBarProvider
```

支持把朋友导出的：

```text
CSV
Parquet
```

作为数据源导入 Data Layer。

但必须明确要求调用者指定：

```text
symbol
asset_class
timeframe
source_timezone
timestamp_semantics
```

Local Provider 一样经过：

```text
Source Snapshot
↓
Normalization
↓
Validation
↓
Frozen Store
↓
Manifest
```

不能因为是本地 CSV 就绕过审计链路。

这样后续朋友给我们：

```text
EURUSD 5m
EURUSD 15m
EURUSD 1h
```

的数据时可以立即使用。

等实际 Provider 确定后，再增加对应 Provider。

---

# 12. DataStore V3

保留当前：

```text
Immutable Files
Dataset ID
Manifest
SHA-256
Refuse overwrite
```

这些设计。

V3 Bars 路径改成能够表达资产和周期。

例如：

```text
data/normalized/bars/
    forex/
        broker_x/
            15m/
                EURUSD/
                    {dataset_id}/bars.parquet
```

股票例如：

```text
data/normalized/bars/
    equity/
        NASDAQ/
            1d/
                AAPL/
                    {dataset_id}/bars.parquet
```

不要写死：

```text
1d
US
CN
```

---

# 13. Resampling

新增：

```text
quant_lab/data/resample.py
```

用于：

```text
1m → 5m
1m → 15m
5m → 1h
1h → 4h
```

OHLC 聚合标准：

```text
open  = first
high  = max
low   = min
close = last
```

volume / tick_volume / amount：

```text
sum
```

open_interest：

```text
last
```

但是：

**禁止直接无脑调用 `df.resample("4h")`。**

Resampling API 必须要求明确：

```text
target_timeframe
timezone
anchor
```

因为：

```text
00:00~03:59
```

和：

```text
01:00~04:59
```

形成的 4H K 完全不同。

对 Chan 来说这会直接改变：

```text
包含关系
分型
笔
```

因此 resampled dataset 的 Manifest 必须保存 lineage：

```text
source_dataset_id
source_timeframe
target_timeframe
aggregation_timezone
anchor
aggregation_rule
```

不要 silent fill missing bars。

不要 silent deduplicate。

不要 silent repair。

---

# 14. Chan-Core 总体设计

建立：

```text
quant_lab/chan/
```

核心输入不要直接依赖 pandas。

应该接受标准 Bar 对象：

```python
analyzer.update(bar)
```

而不是：

```python
calculate_chan(dataframe)
```

允许以后提供：

```python
analyzer.extend(bars)
```

作为便利接口，但内部仍然逐 bar 增量执行。

核心流程：

```text
Raw Bar
   ↓
InclusionProcessor
   ↓
Merged Bar
   ↓
FractalDetector
   ↓
Fractal
   ↓
StrokeBuilder
   ↓
Stroke
```

最外层：

```python
ChanAnalyzer
```

协调各组件。

---

# 15. 学习 Vespa 的设计方式

重点学习：

## 15.1 对象与状态管理器分离

类似 Vespa：

```text
CBi
```

负责：

```text
一笔是什么
```

而：

```text
CBiList
```

负责：

```text
笔怎么创建
怎么更新
什么时候替换
什么时候确认
```

我们的设计：

```text
Stroke
```

只作为结构对象。

```text
StrokeBuilder
```

负责状态机。

同理：

```text
MergedBar
```

是对象。

```text
InclusionProcessor
```

负责增量处理。

---

## 15.2 增量更新

不要每来一根新 K：

```text
重新扫描全部历史
```

目标：

```python
analyzer.update(new_bar)
```

只更新尾部受影响状态。

当前阶段不要过早优化，但不能写明显的每根 K O(N) 全量重算。

---

## 15.3 tentative / confirmed

重点学习 Vespa 的：

```text
sure
virtual
```

思想。

但我们自己的名字使用：

```text
TENTATIVE
CONFIRMED
```

不要直接复制 Vespa API。

---

# 16. Chan-Core 当前确定规则

以下规则是本项目自己的规则。

必须严格实现。

不要用其它缠论版本覆盖。

---

## 16.1 K线方向判断

只使用：

```text
High
Low
```

不使用：

```text
Open
Close
K线颜色
```

对于两个已经无包含关系的 K：

上涨：

```text
后 High > 前 High
AND
后 Low > 前 Low
```

下降：

```text
后 High < 前 High
AND
后 Low < 前 Low
```

---

# 17. 包含关系

如果：

```text
K1.high >= K2.high
AND
K1.low <= K2.low
```

或者反过来：

```text
K2.high >= K1.high
AND
K2.low <= K1.low
```

则存在包含关系。

处理方向来自：

```text
发生包含之前最近已经确定的 K 线方向
```

不是：

```text
Open / Close
红绿K
```

---

## 向上包含处理

```python
new_high = max(k1.high, k2.high)
new_low  = max(k1.low,  k2.low)
```

口诀：

```text
高点取高
低点取高
```

---

## 向下包含处理

```python
new_high = min(k1.high, k2.high)
new_low  = min(k1.low,  k2.low)
```

口诀：

```text
高点取低
低点取低
```

---

# 18. 包含处理必须是顺序增量的

例如：

```text
K0
K1
K2
K3
```

如果：

```text
K1 + K2
```

合并成：

```text
M1
```

下一步必须比较：

```text
M1 vs K3
```

不能继续拿旧的 K2 比较。

所以：

```text
Raw Bars
```

与：

```text
Merged Bars
```

必须保留清晰 lineage。

MergedBar 至少保存：

```text
high
low

start_timestamp
end_timestamp

raw_bars / raw_indices
direction
```

避免丢失：

```text
这根缠K是由哪些原始K组成
```

---

# 19. 初始方向问题不要私自猜

当前已知规则没有完全定义：

```text
数据最开始就遇到包含关系
且前面还没有明确上涨/下降方向
```

如何处理。

因此不要偷偷写：

```text
默认 UP
```

除非明确作为 configurable provisional policy。

第一版推荐：

```text
InitialDirectionPolicy
```

至少支持：

```text
ERROR
UP
DOWN
```

默认：

```text
ERROR
```

如果遇到无法确定初始方向的包含：

```text
明确报错
```

而不是静默猜测。

后续等朋友规则确认后再修改默认行为。

---

# 20. 分型

只对：

```text
去除包含关系后的 MergedBar
```

判断。

三根：

```text
K0 K1 K2
```

顶分型：

```text
K1.high > K0.high
K1.high > K2.high

K1.low > K0.low
K1.low > K2.low
```

底分型：

```text
K1.low < K0.low
K1.low < K2.low

K1.high < K0.high
K1.high < K2.high
```

默认使用严格：

```text
>
<
```

不要擅自把：

```text
>=
<=
```

加入。

相同高/低点如何处理属于尚未确认的规则。

---

# 21. Fractal Model

Fractal 至少保存：

```text
type:
    TOP
    BOTTOM

left
center
right

pivot_time
confirmed_at

price
```

非常重要：

假设：

```text
K10 K11 K12
```

K11 是顶。

则：

```text
pivot_time = K11.timestamp
```

但是只有 K12 完成以后才能知道 K11 是顶。

所以：

```text
confirmed_at = K12 close / confirmation time
```

图上可以把顶画在 K11。

策略不允许在 K11 当时知道这个顶。

---

# 22. 分型允许重叠

例如：

```text
K0 K1 K2
```

可以形成顶分型。

同时：

```text
K1 K2 K3
```

可以形成底分型。

FractalDetector 可以检测并保存这些 raw fractal candidates。

是否能够形成笔由 StrokeBuilder 决定。

不要在 FractalDetector 里提前过滤所有重叠分型。

---

# 23. 成笔规则

一个底分型连接一个顶分型：

```text
BOTTOM → TOP
```

构成：

```text
UP Stroke
```

一个顶分型连接一个底分型：

```text
TOP → BOTTOM
```

构成：

```text
DOWN Stroke
```

同类型：

```text
TOP → TOP
BOTTOM → BOTTOM
```

不能直接形成新笔。

---

# 24. 笔的距离规则

两个端点分型之间必须至少存在：

```text
1 根 MergedBar
```

这根 K：

```text
既不属于起点分型
也不属于终点分型
```

例如：

```text
K0 K1 K2   Bottom
K3          independent
K4 K5 K6   Top
```

允许成笔。

中心：

```text
K1 → K5
```

因此中心 index：

```text
end_center_index - start_center_index >= 4
```

这里 index 必须是：

```text
MergedBar index
```

不是原始 K index。

---

# 25. 同类型极值替换

如果当前正在形成上涨笔：

```text
Bottom A
    ↓
Top B
```

反向下降笔还没有有效成立。

之后出现：

```text
Top C
```

如果：

```text
C.high > B.high
```

则：

```text
B 不再作为当前上涨笔终点
C 替换 B
```

最终：

```text
A → C
```

仍然是一笔。

不是：

```text
A → B
B → C
```

---

下降完全对称。

如果：

```text
Bottom C.low < Bottom B.low
```

则新的更低 Bottom 替换旧 Bottom。

---

# 26. 更低顶 / 更高底不替换

例如当前上涨笔候选终点：

```text
Top B
```

之后出现：

```text
Top C
```

但：

```text
C.high < B.high
```

则：

```text
B 保持当前最高顶
C 不成为新的笔端点
```

下降同理。

---

# 27. 笔必须满足区间极值 invariant

上涨笔：

```text
起点 Bottom
```

必须是该笔区间有效最低底。

终点 Top：

```text
必须是该笔区间有效最高顶
```

下降笔反过来。

实现时不要只依赖“看起来应该满足”。

增加 invariant check。

如果状态机生成违反该 invariant 的 Stroke：

```text
raise / test fail
```

不要 silent repair。

---

# 28. Stroke 状态

Stroke 定义：

```text
start_fractal
end_fractal
direction
status
```

状态：

```text
TENTATIVE
CONFIRMED
```

理解：

```text
Bottom A → Top B
```

形成第一根上涨笔后：

```text
A → B
```

可以存在，但最后一笔仍然可能被延长。

只有下一根有效：

```text
Top B → Bottom C
```

形成之后：

```text
A → B
```

才变为：

```text
CONFIRMED
```

而：

```text
B → C
```

成为新的：

```text
TENTATIVE
```

因此：

```text
最后一笔通常是 tentative
```

这和朋友说的：

```text
新笔生成才代表上一笔结束
```

一致。

---

# 29. Confirmed 结构不可被未来修改

这是系统硬约束。

未来新 K 可以修改：

```text
当前 tentative stroke
```

但不能修改已经：

```text
CONFIRMED
```

的笔。

如果实现中发现 confirmed stroke 被未来数据重写：

```text
视为严重 bug
```

---

# 30. ChanAnalyzer API

期望类似：

```python
analyzer = ChanAnalyzer(config)

for bar in bars:
    analyzer.update(bar)
```

提供：

```python
analyzer.raw_bars
analyzer.merged_bars
analyzer.fractals
analyzer.strokes
analyzer.confirmed_strokes
analyzer.current_stroke
```

不要让调用者直接修改内部 list。

可以返回：

```text
tuple / immutable view / copy
```

---

# 31. Chan-Core 不依赖 pandas

核心：

```text
combiner
fractal
stroke
analyzer
```

不允许 import：

```text
pandas
yfinance
tushare
matplotlib
```

它应该是纯领域算法。

DataFrame 转 Bar 的 adapter 放在：

```text
data / adapter / caller
```

而不是 Chan-Core。

---

# 32. Strategy 抽象

当前 Backtest 不应该继续直接调用：

```python
calculate_signals(...)
```

定义 Strategy Protocol。

概念 API：

```python
class Strategy(Protocol):
    def reset(...): ...
    def on_bar(self, context, bar): ...
```

返回：

```text
OrderIntent
```

或者：

```text
TargetPosition
```

选一个清晰模型即可。

不要同时搞两套。

---

# 33. SMA Strategy 迁移

把现有 SMA 移到：

```text
quant_lab/strategies/sma.py
```

并实现新的 Strategy 接口。

必须保证旧实验：

```text
Signal timing
T close
T+1 open
```

以及结果全部不变。

不要因为重构改变：

```text
rolling window
warmup
execution timing
benchmark timing
```

---

# 34. Chan Strategy 暂时只建骨架

创建：

```text
quant_lab/strategies/chan_fx.py
```

但现在不要擅自实现朋友的最终买卖规则。

可以提供：

```python
class ChanFxStrategy:
```

并接入：

```text
ChanAnalyzer
```

但如果具体交易规则尚未定义：

```text
明确 NotImplemented
```

或者只提供结构观察/debug 模式。

不要自己发明：

```text
买一
买二
背驰
突破
```

---

# 35. Backtest Engine

改为：

```text
BacktestEngine
```

负责：

```text
按时间推进
调用 Strategy
执行下一时点订单
更新 Portfolio
记录状态
```

不应该知道：

```text
SMA fast_window
SMA slow_window
Chan fractal
```

---

# 36. Execution Model

当前 Equity Execution 逻辑保留为：

```text
EquityCashExecutionModel
```

继续支持：

```text
long only
integer share
all cash
commission
slippage
next open
```

保证旧 SPY regression。

同时定义通用：

```text
ExecutionModel
```

接口。

不要现在实现完整 Forex broker simulation。

可以预留：

```text
FxExecutionModel
```

但如果：

```text
spread
lot size
leverage
margin
swap
short
```

规则尚未确认，则不要擅自实现。

---

# 37. Portfolio

当前：

```text
cash + integer quantity
```

是 Equity Portfolio。

重构成：

```text
EquityPortfolio
```

不要硬改成一个塞满：

```python
if asset_class == ...
```

的超级 Portfolio。

未来：

```text
FxPortfolio
```

可以单独实现。

---

# 38. Metrics 和 Intraday

当前 `252` 年化不能直接用于：

```text
5m bar return
```

因此支持 intraday backtest 后：

默认绩效统计应该基于：

```text
Daily Equity Snapshot
```

即：

```text
每天最后一个 equity
↓
daily return
↓
CAGR
Volatility
Sharpe
Sortino
Drawdown
```

Bar-level equity 仍然保存。

但年化风险指标默认基于 daily return。

报告中记录：

```text
metrics_frequency = daily
```

不要把：

```text
每根 5m bar
```

直接乘：

```text
252
```

---

# 39. Config 重构

配置不要继续把 SMA 参数放在顶层。

目标：

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
```

Chan：

```yaml
strategy:
  name: chan_fx
  params: {}

data:
  symbol: EURUSD
  asset_class: forex
  timeframe: 15m
  price_basis: raw
```

Chan 自身规则可以放：

```yaml
chan:
  initial_direction_policy: error
```

目前不要增加几十个无意义配置。

已经明确的规则直接作为默认规则。

只有：

```text
尚未完全确定
或真正需要实验
```

的行为才配置化。

---

# 40. Testing：Data Layer

必须增加：

```text
tests/data_v3/
```

至少覆盖：

```text
1m / 15m / 1h timestamp
UTC timezone
duplicate timestamp
invalid OHLC
optional volume
tick_volume
open_interest
asset class
venue
provider symbol
V2 compatibility
V3 manifest
store immutable
SHA verification
resample
resample anchor
resample timezone
```

---

# 41. Testing：Chan Combiner

至少建立以下 case：

### Case 1

无包含：

```text
K0 → K1 up
```

不合并。

### Case 2

无包含：

```text
K0 → K1 down
```

不合并。

### Case 3

上涨中的包含：

```text
high = max
low = max
```

### Case 4

下降中的包含：

```text
high = min
low = min
```

### Case 5

连续包含：

```text
K1 + K2 → M1
M1 + K3 → M2
```

验证一定是：

```text
M1 vs K3
```

不是：

```text
K2 vs K3
```

### Case 6

检查 raw lineage 没丢。

---

# 42. Testing：Fractal

至少覆盖：

```text
标准顶
标准底
连续上涨
连续下降
不满足分型
相等 high
相等 low
重叠分型
```

相等情况按当前 strict rule：

```text
不构成
```

---

# 43. Testing：Stroke

重点覆盖：

### 43.1

```text
012 Bottom
3   independent
456 Top
```

可以成笔。

### 43.2

```text
012 Bottom
345 Top
```

不能成笔。

### 43.3

```text
Bottom
→ Top
```

一笔。

### 43.4

```text
Bottom
→ Top
→ Bottom
```

两笔。

### 43.5

同类型更高顶：

```text
Bottom A
Top B
Top C > B
```

最终：

```text
A → C
```

仍然一笔。

### 43.6

同类型更低顶：

```text
Top C < Top B
```

保持 B。

### 43.7

更低 Bottom：

```text
Bottom C < Bottom B
```

替换。

### 43.8

新的反向 Stroke 形成后：

```text
上一 Stroke → CONFIRMED
新 Stroke → TENTATIVE
```

---

# 44. Prefix Invariance Test

新增 Chan 专属的：

```text
Prefix Invariance Test
```

例如：

第一次：

```text
输入 K0 ~ K100
```

记录：

```text
所有 CONFIRMED fractal / stroke
```

然后：

```text
继续输入 K101 ~ K1000
```

必须保证：

```text
K100 时已经 CONFIRMED 的结构完全不变
```

允许变化：

```text
最后 tentative structure
```

不允许变化：

```text
confirmed history
```

这是防止 future leakage 的核心测试。

---

# 45. Future Mutation Test

现有项目已经有 Future Mutation Test。

继续保留。

并为 Chan-Core 增加类似：

```text
修改 cutoff 之后所有未来 OHLC
```

验证 cutoff 之前已经：

```text
confirmed_at <= cutoff
```

的结构完全不变。

注意比较：

```text
confirmed_at
```

而不是：

```text
pivot_time
```

---

# 46. Golden Fixtures

创建：

```text
tests/fixtures/chan/
```

支持 JSON / CSV fixture。

格式应能够人工标注：

```text
raw bars
expected merged bars
expected fractals
expected strokes
```

以后朋友给出人工标注以后，我们会不断加入：

```text
Golden Samples
```

最终：

```text
朋友的定义
```

才是最高标准。

不是：

```text
Vespa 输出
CZSC 输出
其他库输出
```

---

# 47. Debug / Inspection 工具

增加简单脚本：

```text
scripts/inspect_chan.py
```

例如：

```bash
python scripts/inspect_chan.py \
  --dataset-id xxx \
  --symbol EURUSD \
  --start ... \
  --end ...
```

输出：

```text
Raw Bars
Merged Bars
Fractals
Strokes
```

支持 CSV / JSON dump。

暂时不需要复杂 GUI。

如果简单，可以生成 matplotlib 图：

```text
K线
+
顶/底分型 marker
+
笔
```

但绘图模块不得进入 chan-core。

---

# 48. Documentation

新增：

```text
docs/chan-core.md
```

必须记录：

```text
我们自己的规则
```

而不是复制传统缠论文章。

明确写：

```text
1. 包含关系
2. 向上处理
3. 向下处理
4. 分型
5. 分型确认时间
6. 成笔距离
7. 更高顶替换
8. 更低底替换
9. tentative
10. confirmed
11. 当前尚未确定的规则
```

增加：

```text
docs/architecture.md
```

说明：

```text
Data
Chan
Strategy
Backtest
Execution
Portfolio
```

之间依赖方向。

---

# 49. 明确记录尚未确认的 Chan 问题

不要偷偷解决。

至少记录：

```text
1. 最开始就发生 K 线包含时，没有前序方向怎么办？

2. high / low 相等时分型怎么定义？

3. high / low 相等时同类型端点是否替换？

4. gap 是否影响成笔距离？

5. 是否存在额外成笔价格关系限制？

6. 未来是否还有线段、中枢的自定义规则？
```

当前第一版行为：

```text
initial inclusion:
    default ERROR

equal fractal:
    strict，不构成

gap:
    不额外算一根 K

额外价格关系:
    暂无
```

任何 provisional behavior 都要：

```text
代码注释
文档
测试
```

三者一致。

---

# 50. 不要过度抽象

不要因为未来可能支持：

```text
股票
外汇
期货
Crypto
期权
```

就构造几十层：

```text
AbstractFactory
PluginManager
RegistryFactory
MetaProvider
```

目标是：

```text
接口清晰
容易扩展
目前代码简单
```

优先使用：

```text
dataclass
Enum
Protocol
小的 service class
```

---

# 51. 不要引入数据库

当前阶段继续：

```text
Parquet
JSON Manifest
SHA
```

即可。

不要引入：

```text
PostgreSQL
DuckDB
Redis
MongoDB
```

除非现有需求确实无法解决。

---

# 52. 不要引入实时交易系统

这次不做：

```text
WebSocket
Live Trading
Broker Order API
Paper Trading
异步撮合系统
```

只把：

```text
数据模型
Chan
Strategy
Backtest
```

的边界设计正确。

---

# 53. 实施顺序

请严格分阶段实施。

## Phase 1：Package 重构

完成：

```text
pyproject.toml
src/quant_lab/
```

迁移现有模块。

保留 compatibility wrapper。

验收：

```bash
python -m pytest -q
```

全部通过。

SPY regression 不变。

---

## Phase 2：Market / Data V3

实现：

```text
AssetClass
Timeframe
Canonical Bar V3
Manifest V3
V2 compatibility
generic validation
generic store path
```

仍保证旧数据可用。

---

## Phase 3：Local Forex Data

实现：

```text
LocalBarProvider
```

能够导入：

```text
Forex CSV / Parquet
```

并明确：

```text
timezone
timeframe
symbol
provider_symbol
timestamp semantics
```

---

## Phase 4：Resampling

实现：

```text
1m → 5m / 15m / 1h / 4h
```

显式：

```text
timezone
anchor
lineage
```

---

## Phase 5：Chan-Core

依次实现：

```text
models
combiner
fractal
stroke
analyzer
```

先测试 primitive。

不要先写大一统 `analyzer.py` 再补测试。

---

## Phase 6：Backtest Strategy Interface

抽离：

```text
Strategy
BacktestEngine
ExecutionModel
Portfolio
```

把 SMA 迁过去。

必须保持旧实验结果。

---

## Phase 7：Chan Integration

允许：

```text
Strategy
```

消费：

```text
ChanAnalyzer
```

但是暂时不要发明完整交易逻辑。

---

## Phase 8：Docs + Inspection

完成：

```text
chan-core.md
architecture.md
inspect_chan.py
```

---

# 54. 每个阶段提交要求

尽量按阶段产生独立 commit。

例如：

```text
refactor: migrate project to quant_lab package

feat(data): add generic market bar v3

feat(data): add local forex provider

feat(data): add anchored timeframe resampling

feat(chan): add inclusion processor

feat(chan): add fractal detector

feat(chan): add stroke state machine

refactor(backtest): add strategy and execution interfaces

docs: document chan-core rules and architecture
```

不要把全部修改塞进一个巨大 commit。

---

# 55. 验收标准

最终必须达到：

```text
[1] 现有全部 pytest 通过

[2] SPY frozen regression 完全不变

[3] V1/V2 数据仍然可读取

[4] 新 V3 可保存 multi-timeframe dataset

[5] schema 不再把 1d 写死

[6] schema 不再只支持 US/CN

[7] Forex 可以没有真实 volume

[8] 支持 tick_volume

[9] Timeframe 至少支持
    1m / 5m / 15m / 30m / 1h / 4h / 1d

[10] Resampling 必须显式 timezone + anchor

[11] Chan-Core 不依赖 pandas

[12] Chan-Core 使用增量 update(bar)

[13] K线包含逻辑有完整单测

[14] 分型有完整单测

[15] 笔距离有完整单测

[16] 更高顶/更低底替换有完整单测

[17] tentative/confirmed 有完整单测

[18] confirmed structure 通过 prefix invariance

[19] Backtest 不再直接依赖 SMA

[20] SMA 历史行为保持一致

[21] 没有实现未经确认的线段/中枢/背驰规则

[22] 所有 provisional Chan 规则都有文档记录
```

---

# 56. 代码质量要求

代码风格遵循当前仓库：

```text
直接
可读
少魔法
少过度抽象
```

不要为了展示设计模式增加无意义 class。

关键状态变化必须容易 debug。

例如 StrokeBuilder 最好可以从代码中直接看出：

```text
当前状态
收到什么 fractal
为什么更新终点
为什么创建新笔
为什么上一笔确认
```

不要把核心状态机藏在大量 callback / generic framework 中。

---

# 57. 先分析再修改

开始开发前，请先输出一份简短分析：

```text
1. 当前 dev 实际目录
2. 当前 Data Layer 的可复用部分
3. 当前存在的 daily/equity hardcode
4. 当前 Backtest 与 SMA 的耦合点
5. Vespa chan.py 中准备借鉴的设计
6. 计划修改的文件
7. 兼容策略
```

确认理解后直接实施。

不需要因为普通工程细节反复询问。

但是如果遇到：

```text
Chan 交易规则本身没有定义
```

不要猜。

保留显式 TODO / provisional behavior，并说明。

---

# 58. 最重要的原则

本项目不是要实现：

```text
“某个标准版本的缠论”
```

而是实现：

```text
我们已经明确、可以程序化、可以回测、可以验证的市场结构规则。
```

Vespa314/chan.py 是：

```text
architecture reference
engineering reference
state-machine reference
```

不是：

```text
behavior oracle
```

最终正确性优先级：

```text
朋友明确给出的规则
        >
本项目 Golden Fixtures
        >
本项目单元测试
        >
其它开源缠论实现
```

请按这个原则实施。
```
````
