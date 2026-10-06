# Quant Lab 小范围架构清理方案：统一 Instrument 模型 + 清理日线专用 Helper

仓库：

https://github.com/aqwddda/quant-lab

目标分支：

```text
dev
```

请直接基于当前最新 `dev` 分支开发。

本轮是一次**小范围架构清理**，不要进行大规模重构，不要修改 Chan-Core 规则，不要扩展 Forex execution。

---

# 1. 本轮目标

本轮只做两件事：

1. 清理当前重复的 Instrument 模型，统一到 `src.market.Instrument`
2. 清理 Provider Base 中残留的日线专用 helper，避免把日线股票逻辑伪装成通用 Provider 能力

明确不做：

```text
bar overlap 校验
Chan-Core 规则修改
Stroke extreme invariant 行为修改
Forex execution
Forex short / leverage / lot / spread / margin / swap
最终 Chan-FX 交易规则
```

---

# 2. 当前问题一：存在两套 Instrument 模型

当前正式领域模型已经存在：

```python
src.market.Instrument
```

当前字段大致为：

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

这是未来统一服务于：

```text
equity
forex
futures
```

的正式 Instrument 模型。

但是当前 Data Layer 中仍然保留了一套旧式 Instrument DataFrame schema：

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

对应代码主要存在于：

```text
src/data/schema.py
src/data/validation.py
src/data/normalization/
src/data/store.py
scripts/download_data.py
```

并且 validator 中仍然存在：

```python
market in {"US", "CN"}
```

之类的旧股票模型假设。

这导致项目里实际上存在两套 Instrument 定义：

```text
src.market.Instrument
```

和：

```text
INSTRUMENT_COLUMNS + validate_instruments()
```

这与当前项目“一个功能，一个实现，一个 source of truth”的原则冲突。

---

# 3. 最终原则：Instrument 只有一个 source of truth

正式 Instrument 定义只能是：

```python
src.market.Instrument
```

最终数据流应当是：

```text
Provider
    ↓
Source Snapshot
    ↓
Normalization
    ↓
src.market.Instrument
    ↓
Manifest / DataStore
```

不要继续保留：

```text
Provider
    ↓
旧 instruments DataFrame
    ↓
instruments_from_reference(...)
    ↓
src.market.Instrument
```

如果中间 Instrument DataFrame 没有独立研究价值，就删除。

---

# 4. 重点检查文件

请重点检查：

```text
src/data/schema.py
src/data/validation.py
src/data/normalization/__init__.py
src/data/normalization/yahoo.py
src/data/normalization/tushare.py
src/data/store.py
src/data/loader.py
src/data/providers/
scripts/download_data.py
tests/data/
README.md
docs/architecture.md
AGENTS.md
```

重点关注：

```text
INSTRUMENT_COLUMNS
validate_instruments(...)
instruments_from_reference(...)
normalized_frames["instruments"]
VALIDATORS["instruments"]
market
exchange
asset_type
currency
list_date
delist_date
```

---

# 5. Yahoo / Tushare normalization 改造

Yahoo / Tushare normalization 不再生成一套旧式 canonical Instrument DataFrame。

应该直接构造：

```python
Instrument(...)
```

例如 Yahoo：

```python
Instrument(
    symbol="AAPL",
    provider_symbol="AAPL",
    asset_class=AssetClass.EQUITY,
    venue="NASDAQ",
    quote_currency="USD",
)
```

Tushare 同理。

如果 Provider 返回的是供应商自己的 exchange code，例如：

```text
NMS
NYQ
SZSE
SSE
```

请明确完成：

```text
provider metadata
→ canonical Instrument
```

转换。

不要把 provider 原始字段直接冒充项目领域模型。

---

# 6. Provider 原始 metadata 仍然必须冻结

删除旧 canonical Instrument DataFrame，不代表删除 Provider 原始证券信息。

例如 Yahoo：

```python
ticker.get_info()
```

仍然应该作为 Source Snapshot 冻结。

Tushare 原始 instrument/reference response 同理。

正确边界：

```text
Supplier metadata
    ↓
freeze source
    ↓
normalize
    ↓
src.market.Instrument
```

必须保留 provenance。

---

# 7. Manifest 继续保存正式 Instrument

当前 Manifest 已经使用：

```text
manifest["instruments"]
```

并通过：

```python
Instrument(**item)
```

进行验证。

这一方向保留。

Manifest 中的 instrument schema 必须与：

```python
src.market.Instrument
```

保持一致。

不要再支持第二套 Instrument manifest schema。

---

# 8. DataStore 清理

如果当前存在：

```python
VALIDATORS = {
    ...
    "instruments": validate_instruments,
}
```

并且 `normalized_files["instruments"]` 只是旧设计遗留，则删除。

正式 instrument metadata 已经存在于：

```text
manifest["instruments"]
```

不需要再额外保存一份 canonical instrument parquet。

如果某个 reference table 确实有独立研究价值：

- 不要继续叫 `instruments`
- 不要承担 canonical Instrument 职责
- 使用更明确的 provider/reference 命名

本轮没有明确需求则不要新增。

---

# 9. 不要把旧字段重新塞进通用 Instrument

不要为了兼容旧 schema，把下面字段全部加回 `src.market.Instrument`：

```text
name
market
provider
list_date
delist_date
asset_type
```

正式 Instrument 应继续保持跨资产通用。

如果未来确实需要：

```text
name
list_date
delist_date
```

可以单独设计 reference metadata。

本轮不要提前实现。

---

# 10. 当前问题二：Provider Base 中混入了日线专用逻辑

当前：

```text
src/data/providers/base.py
```

同时存在真正通用的：

```python
ProviderCapabilities
BarProvider
```

和类似：

```python
def check_request(symbol, start, end, frequency="1d"):
    ...
    if frequency != "1d":
        raise ...
```

这种实际上只服务于：

```text
Yahoo / Tushare Daily Equity
```

的 helper。

这会造成错误语义：

```text
providers/base.py
```

看起来是通用层，但内部假设所有 Provider 都是日线。

需要清理。

---

# 11. Provider Base 最终职责

`src/data/providers/base.py` 应只保留真正通用的内容，例如：

```text
ProviderCapabilities
BarProvider Protocol
通用 identity / capability 约束
```

不要在 Base 层写死：

```text
1d
YYYY-MM-DD
US
CN
```

等日线股票假设。

---

# 12. 日线请求 helper 的处理方式

当前 `check_request(...)` 如果只被 Yahoo / Tushare 使用，请改成语义明确的日线 helper。

建议：

```python
check_daily_date_request(...)
```

可放在例如：

```text
src/data/providers/_daily.py
```

或者其它明确表示：

```text
daily equity provider helper
```

的位置。

不要继续：

```python
check_request(...)
```

并放在通用 `base.py` 中。

---

# 13. 不要因此扩展 Yahoo / Tushare intraday

本轮只是整理职责。

Yahoo / Tushare 当前仍然只声明：

```text
AssetClass.EQUITY
Timeframe.D1
```

这是允许的。

不要为了“通用化”擅自增加：

```text
Yahoo 1m
Yahoo 5m
Tushare intraday
```

能力。

Provider 实际能力继续由：

```python
ProviderCapabilities
```

声明。

---

# 14. LocalBarProvider 必须保持真正通用

Local Provider 当前负责：

```text
1m
5m
15m
30m
1h
4h
1d
```

以及：

```text
equity
forex
futures
```

的本地导入能力。

确认：

```text
src/data/providers/local.py
```

不依赖：

```text
daily request helper
US/CN
date-only request
```

。

不要改坏 Local Provider。

---

# 15. 本轮明确禁止修改 Chan-Core

不要修改以下文件的算法行为：

```text
src/chan/combiner.py
src/chan/fractal.py
src/chan/stroke.py
src/chan/analyzer.py
```

尤其不要修改：

```text
包含规则
初始方向
严格分型
笔距离
同类极值替换
tentative / confirmed
区间极值 invariant
```

当前这些规则仍需要进一步人工确认。

如果无需改 import，Chan-Core 不要动。

---

# 16. 不要增加 bar overlap 校验

当前关于：

```text
相邻 canonical bars 是否允许时间区间 overlap
```

的问题暂时不修改。

不要趁本轮给：

```python
validate_bars(...)
```

增加 overlap business rule。

这一条后续单独确认。

---

# 17. 不要修改 Stroke extreme invariant 行为

如果当前某些走势可能触发：

```text
Stroke endpoint extreme invariant violated
```

本轮保持现状。

不要自行设计回滚、重选起点、重构笔等规则。

---

# 18. 不要实现 Forex execution

禁止修改：

```text
FxExecutionModel
TargetPosition
EquityPortfolio
ChanFxStrategy
```

去支持：

```text
short
lot
leverage
margin
spread
swap
```

。

这些等朋友的真实交易规则确定后再做。

---

# 19. 测试要求

测试中必须明确：

```python
src.market.Instrument
```

是唯一正式 Instrument 模型。

至少覆盖：

```text
Equity
Forex
Futures
provider_symbol != symbol
base_currency
quote_currency
tick_size
lot_size
contract_multiplier
expiry
```

Yahoo / Tushare 测试需要验证：

```text
Provider raw metadata
→ Source Snapshot
→ Normalization
→ src.market.Instrument
→ Manifest
```

DataStore 测试需要验证：

```python
manifest["instruments"]
```

使用正式 Instrument schema，不再要求：

```text
normalized_files["instruments"]
```

存在。

Local Provider 的多资产、多周期能力必须保持不变。

---

# 20. 全仓搜索

完成后运行类似：

```bash
grep -R "INSTRUMENT_COLUMNS" src tests scripts
grep -R "validate_instruments" src tests scripts
grep -R "instruments_from_reference" src tests scripts
grep -R "check_request" src tests scripts
grep -R "market.*US.*CN" src tests scripts
grep -R "asset_type" src tests scripts
```

逐项人工判断。

目标不是机械清零所有字符串。

目标是：

> 不再存在第二套 canonical Instrument 模型。

Provider 原始 metadata 中出现：

```text
asset_type
exchange
market
```

可以存在，但必须明确属于供应商语义。

---

# 21. 文档同步

更新：

```text
README.md
docs/architecture.md
AGENTS.md
```

明确：

```text
src.market.Instrument
```

是唯一 canonical Instrument。

不要再把：

```text
normalized instruments table
```

描述成正式领域模型。

同时说明：

```text
Yahoo / Tushare:
    Equity + Daily Provider

LocalBarProvider:
    explicit multi-asset / multi-timeframe import
```

---

# 22. 不要增加新的架构层

不要新增：

```text
InstrumentService
InstrumentRepository
MetadataRegistry
ProviderFactory hierarchy
```

之类的抽象。

期望结构保持简单：

```text
Provider
    ↓
Normalization
    ↓
Instrument dataclass
    ↓
Manifest
```

---

# 23. 推荐执行顺序

1. 检查 Yahoo / Tushare / Local 当前 Instrument 数据流
2. 删除旧 `INSTRUMENT_COLUMNS / validate_instruments / instruments_from_reference`，前提是它们只服务旧 canonical Instrument DataFrame
3. Yahoo / Tushare normalization 直接生成 `Instrument` 或 `list[Instrument]`
4. 修改 `scripts/download_data.py` 和 `DataStore.save_dataset(...)` 直接使用正式 Instrument
5. 删除 `normalized_files["instruments"]` 和 `VALIDATORS["instruments"]` 等旧路径
6. 从 `providers/base.py` 移出日线 request helper
7. 修复测试、README、architecture、AGENTS
8. 运行全量测试和 grep 检查

---

# 24. 验收标准

完成后：

```bash
python -m pytest -q
```

必须全部通过当前有效测试。

同时确认：

```text
[1] src.market.Instrument 是唯一正式 Instrument
[2] 不再存在第二套 canonical INSTRUMENT_COLUMNS schema
[3] 不再存在旧 canonical validate_instruments
[4] Yahoo / Tushare 直接产出正式 Instrument
[5] Manifest 继续保存并验证正式 Instrument
[6] DataStore 不再依赖 normalized instrument parquet
[7] Provider Base 不再包含 Daily-only request 规则
[8] Yahoo / Tushare 仍然只支持 Equity + 1d
[9] Local Provider 的多资产多周期能力不受影响
[10] Chan-Core 行为完全未修改
[11] bar overlap validation 完全未修改
[12] Forex execution 完全未修改
```

---

# 25. 最终开发报告

完成后输出：

## Removed

删除了哪些：

```text
旧 Instrument schema
旧 validator
旧 normalized instrument frame
旧 helper
```

## Instrument Flow

说明现在：

```text
Yahoo / Tushare / Local
→ Source Snapshot
→ Normalization
→ src.market.Instrument
→ Manifest
```

如何流转。

## Daily Helper

说明原来的：

```text
check_request
```

现在放在哪里、叫什么，以及为什么它不再属于通用 Provider Base。

## Untouched

明确确认以下行为未修改：

```text
Chan-Core
bar overlap validation
Stroke extreme invariant
Forex execution
Chan trading rules
```

## Tests

给出：

```text
passed
failed
```

以及主要相关测试文件。

---

# 26. 最终原则

本轮不是继续加功能。

目标只是把当前架构进一步收紧：

```text
一个领域概念
→ 一个模型

一个职责
→ 一个正式位置
```

最终：

```text
Instrument
→ src.market.Instrument

Provider Base
→ 只保存真正通用能力

Daily Equity request
→ 属于 Daily Equity Provider 自己
```

不要借本轮任务继续扩展理论、执行系统或交易能力。
