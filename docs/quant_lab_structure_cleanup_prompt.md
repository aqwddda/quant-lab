# Quant Lab 结构清理任务：去除 `src/quant_lab` 套娃、彻底删除旧版兼容层

## 0. 背景

仓库：

https://github.com/aqwddda/quant-lab

目标分支：

```text
dev
```

请直接基于当前最新 `dev` 分支工作。

前一阶段已经完成：

- Data Layer V3 / 多资产多周期改造
- market domain
- chan-core
- strategies
- backtest engine
- resampling
- local provider
- 新测试
- 新文档

这些新功能**不要推翻，不要重新设计，不要回滚**。

这次任务的重点不是重新开发功能，而是：

> 对当前已经开发完成的代码做一次彻底的目录与兼容层清理。

---

# 1. 当前结构存在严重问题

目前代码形成了这种结构：

```text
src/
├── __init__.py
│
├── data/
│   ├── loader.py
│   ├── schema.py
│   ├── store.py
│   └── ...
│
├── backtest.py
├── strategy.py
├── execution.py
├── portfolio.py
├── metrics.py
├── validation.py
├── data_loader.py
│
└── quant_lab/
    ├── __init__.py
    ├── market/
    ├── data/
    ├── chan/
    ├── strategies/
    ├── backtest/
    └── validation.py
```

实际上：

```text
src/quant_lab/
```

里面才是新的真实实现。

而外层：

```text
src/data/
src/backtest.py
src/strategy.py
...
```

大量已经变成 compatibility wrapper。

例如当前：

```python
# src/data/loader.py

"""Compatibility module; use quant_lab.data.loader."""
import sys
from importlib import import_module
sys.modules[__name__] = import_module("quant_lab.data.loader")
```

这种结构本项目不接受。

---

# 2. 本次最重要的要求

## 不要 `src/quant_lab`

最终必须删除整个：

```text
src/quant_lab/
```

目录。

不是保留。

不是 alias。

不是 compatibility wrapper。

不是 namespace package。

是：

```text
DELETE
```

---

# 3. 最终目录目标

把当前 `src/quant_lab/*` 的真正实现**整体上移一级**。

最终希望得到：

```text
src/
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
│   ├── models.py
│   ├── schema.py
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
├── backtest/
│   ├── __init__.py
│   ├── models.py
│   ├── engine.py
│   ├── execution.py
│   ├── portfolio.py
│   └── metrics.py
│
└── validation.py
```

也就是说：

```text
src
```

就是项目源码根目录。

**不要再在 `src` 下创建第二层项目名目录。**

---

# 4. Import 风格

项目继续使用现在原仓库习惯的：

```python
from src.data.loader import ...
from src.chan import ChanAnalyzer
from src.market.models import ...
from src.strategies.base import ...
from src.backtest.engine import ...
```

不要变成：

```python
from quant_lab.xxx import ...
```

也不要变成：

```python
from data.xxx import ...
```

统一使用：

```text
src.xxx
```

---

# 5. 这次不要再保留 compatibility wrappers

这是一个非常重要的要求。

当前类似：

```python
sys.modules[__name__] = import_module("quant_lab.xxx")
```

的 compatibility 文件全部删除。

包括但不限于：

```text
src/backtest.py
src/strategy.py
src/execution.py
src/portfolio.py
src/metrics.py
src/data_loader.py

以及 src/data/ 下指向 quant_lab.data.* 的 wrapper
```

如果新代码已经有：

```text
src/backtest/
src/strategies/
src/data/
```

那么旧的同功能入口直接删除。

不要保留：

```text
Deprecated wrapper
Compatibility alias
Legacy import path
Re-export module
```

---

# 6. 不需要兼容 V1

再次强调：

> 当前 dev 不需要继续支持旧 V1 代码结构。

旧 V1 已经通过 Git tag / GitHub Release 固化。

历史版本如果以后需要：

```text
checkout tag
```

即可。

当前开发分支应该代表：

```text
新的正确架构
```

而不是：

```text
新架构 + 所有历史包袱
```

---

# 7. 删除 V1 专属逻辑

请完整审查当前仓库，删除只为了兼容旧 V1 而存在的代码。

重点检查：

```text
legacy
compatibility
v1
legacy_provider_adjusted
legacy_path
download_legacy
_legacy_file
legacy metadata
legacy SPY regression
old API wrapper
old import wrapper
```

原则：

如果一段代码存在的唯一理由是：

```text
“让以前的 V1 调用方式还能继续跑”
```

直接删除。

---

# 8. 删除 legacy SPY 特殊通道

之前为了复现第一版 SPY SMA 实验，项目保留了：

```text
legacy_provider_adjusted
```

以及：

```text
data/raw/spy_daily.parquet
legacy metadata
legacy loader
legacy regression
```

这一整套兼容逻辑现在都不再需要。

请删除代码中所有：

```text
legacy_provider_adjusted
```

相关特殊分支。

Data Layer 只保留现在正式的数据模型和正式 data pipeline。

不要再让 loader 出现类似：

```python
if price_basis == "legacy_provider_adjusted":
    ...
```

---

# 9. 删除 V1 Loader

如果当前仍存在：

```text
src/data_loader.py
```

作为旧入口：

删除。

只保留：

```text
src/data/loader.py
```

作为正式 Loader。

---

# 10. 删除 V1 Strategy 入口

如果当前：

```text
src/strategy.py
```

只是为了兼容旧：

```python
calculate_signals(...)
```

调用：

删除。

正式策略全部进入：

```text
src/strategies/
```

例如：

```text
src/strategies/sma.py
src/strategies/chan_fx.py
```

---

# 11. 删除旧单文件 Backtest 入口

如果：

```text
src/backtest.py
```

已经只是 compatibility wrapper：

删除。

正式实现只保留：

```text
src/backtest/
```

---

# 12. Execution / Portfolio / Metrics 同样处理

如果：

```text
src/execution.py
src/portfolio.py
src/metrics.py
```

只是旧 import compatibility：

全部删除。

正式代码：

```text
src/backtest/execution.py
src/backtest/portfolio.py
src/backtest/metrics.py
```

作为唯一实现。

---

# 13. Data V2 / V3 不需要“双轨兼容”

前一个任务中为了兼容旧版本，可能保留了：

```text
Schema V2 reader
Schema V3 reader
V2 manifest compatibility
legacy daily schema
date → timestamp adapter
```

请重新审查。

原则改为：

> 当前 dev 只维护现在正式的数据 schema。

如果新的正式 schema 已经是：

```text
timestamp
symbol
OHLC
asset_class
venue
timeframe
...
```

那么旧：

```text
date-only daily schema
US/CN-only schema
V2 manifest compatibility
```

如果只是为了读取旧版本数据：

**删除。**

不要因为旧 tag 里面使用过就继续保留。

---

# 14. Manifest 只维护当前正式版本

如果当前代码中存在：

```python
if schema_version == 1:
    ...
elif schema_version == 2:
    ...
elif schema_version == 3:
    ...
```

请检查原因。

如果 `1/2` 只是历史版本兼容：

删除。

当前 dev 的 manifest validator 可以明确只支持：

```text
当前正式 schema version
```

例如：

```text
schema_version = 3
```

旧数据交给旧 release/tag 读取。

这比在当前代码里面永久维护迁移逻辑更简单。

---

# 15. 不要为了旧测试保留旧代码

这是此次任务和上一次任务最大的区别。

如果：

```text
测试 A
```

只是在验证：

```text
V1 compatibility
legacy SPY
legacy import
legacy path
```

那么：

> 删除测试 A。

不要为了“让所有旧 pytest 继续通过”而保留废弃架构。

我们的目标不是：

```text
历史所有测试一个不删
```

而是：

```text
当前架构应该保留的行为都有测试
当前已经废弃的行为连代码和测试一起删掉
```

---

# 16. 明确删除这个测试

如果仍存在：

```text
tests/test_legacy_spy_regression.py
```

删除。

除非其中有某个测试验证的是通用回测正确性。

如果有通用价值：

把通用部分迁移到：

```text
tests/backtest/
```

不要保留：

```text
legacy
SPY V1
旧 SHA
旧特殊 dataset
```

绑定。

---

# 17. `tests/data` 与 `tests/data_v3` 也不要双轨

当前现在同时存在：

```text
tests/data/
tests/data_v3/
```

请重新整理。

不要最终留下：

```text
data
data_v3
```

这种“新旧两套数据层”。

目标应该只有：

```text
tests/data/
```

然后里面测试的是：

```text
当前正式 Data Layer
```

把 `tests/data_v3` 中有效的新测试移入：

```text
tests/data/
```

删除已经过时的旧 Data Layer 测试。

最终不要出现：

```text
v1
v2
v3
legacy
compat
```

这种历史版本目录。

---

# 18. 推荐最终 tests 结构

整理成：

```text
tests/
│
├── conftest.py
├── fixtures/
│   └── chan/
│
├── data/
│   ├── test_schema.py
│   ├── test_validation.py
│   ├── test_manifest.py
│   ├── test_store.py
│   ├── test_loader.py
│   ├── test_resample.py
│   ├── test_local_provider.py
│   ├── test_yahoo_provider.py
│   └── test_tushare_provider.py
│
├── chan/
│   ├── test_combiner.py
│   ├── test_fractal.py
│   ├── test_stroke.py
│   ├── test_analyzer.py
│   └── test_no_lookahead.py
│
├── strategies/
│   ├── test_sma.py
│   └── test_strategy_interface.py
│
└── backtest/
    ├── test_engine.py
    ├── test_execution.py
    ├── test_portfolio.py
    └── test_metrics.py
```

不要求机械完全一致，但方向如此。

---

# 19. 保留新 Chan-Core

当前已经完成的：

```text
src/quant_lab/chan/
```

不要重新实现。

把它移动为：

```text
src/chan/
```

继续保留现在已经实现的：

```text
config.py
enums.py
models.py
combiner.py
fractal.py
stroke.py
analyzer.py
```

只修 import。

不要借这次结构清理偷偷修改缠论行为。

---

# 20. 保留新的 Market 模块

把：

```text
src/quant_lab/market/
```

移动为：

```text
src/market/
```

继续作为：

```text
AssetClass
Timeframe
Bar
Instrument / Market model
```

等跨模块基础模型所在地。

---

# 21. 保留新的 Data Layer

把：

```text
src/quant_lab/data/
```

移动到：

```text
src/data/
```

当前外层 `src/data/` 的 compatibility wrapper 应该被真正实现覆盖。

不是：

```text
wrapper → quant_lab
```

而是：

```text
src/data/loader.py
```

本身就是 Loader 真正代码。

同理：

```text
src/data/store.py
src/data/schema.py
src/data/validation.py
src/data/providers/*
...
```

都应该是真代码。

---

# 22. 保留新的 Backtest

把：

```text
src/quant_lab/backtest/
```

移动为：

```text
src/backtest/
```

不要再保留单文件：

```text
src/backtest.py
```

因为 Python 中同时存在：

```text
backtest.py
backtest/
```

本身也会制造歧义。

---

# 23. 保留新的 Strategies

把：

```text
src/quant_lab/strategies/
```

移动为：

```text
src/strategies/
```

删除：

```text
src/strategy.py
```

---

# 24. Validation 只保留一个明确位置

当前可能同时存在：

```text
src/validation.py
src/data/validation.py
src/quant_lab/validation.py
```

请整理职责。

推荐：

```text
src/data/validation.py
```

只负责：

```text
market data / dataset validation
```

而：

```text
src/validation.py
```

如果仍有价值，则只负责：

```text
future mutation
causality
research validation
```

不要出现第三个：

```text
src/quant_lab/validation.py
```

---

# 25. pyproject.toml

当前 `pyproject.toml` 里面如果存在：

```toml
[tool.setuptools.packages.find]
where = ["src"]
include = ["quant_lab*"]
```

这种配置必须修改。

因为：

```text
quant_lab
```

package 将不存在。

本项目不需要为了 setuptools 的“标准 src layout”再次创造：

```text
src/项目名/
```

。

如果当前项目没有真正需要：

```bash
pip install -e .
```

才能工作的需求：

可以删除 setuptools package discovery 相关配置。

`pyproject.toml` 可以仅保留真正有用的：

```text
project metadata
pytest
tool config
```

或者如果维护 package 安装确有实际价值，就配置成适配当前：

```text
src/
```

结构。

但绝对不能为了 packaging 工具重新引入：

```text
src/quant_lab/
```

。

---

# 26. Scripts Import

完整检查：

```text
scripts/
```

把：

```python
from quant_lab.xxx
```

全部改成：

```python
from src.xxx
```

同时检查是否为了新的 package layout 删除过：

```python
ROOT
sys.path
```

逻辑。

由于脚本可能从任意工作目录执行，确保：

```bash
python scripts/xxx.py
```

从项目根目录正常运行。

不要为了这个重新引入第二层 package。

---

# 27. Tests Import

完整修改：

```python
from quant_lab.xxx
```

为：

```python
from src.xxx
```

禁止留下：

```text
quant_lab
```

相关 import。

---

# 28. Config / Docs 同步

完整检查：

```text
README.md
AGENTS.md
docs/
config/
```

删除所有已经过时的内容，包括：

```text
src/quant_lab
quant_lab.data
quant_lab.chan

V1 compatibility
V2 compatibility
legacy SPY
legacy_provider_adjusted
old import path
```

文档只描述当前实际代码。

不要把旧架构保留在 README 里作为主流程。

Git tag 已经承担历史记录职责。

---

# 29. 不要新增 Migration / Deprecation 文档

不需要：

```text
MIGRATION_V1_TO_V3.md
DEPRECATED.md
legacy compatibility guide
```

当前仓库不是对外发布的长期 Python SDK。

没有必要为了历史 API 背 compatibility contract。

Git 历史和 release/tag 已经足够。

---

# 30. 搜索清零要求

完成后请全仓搜索：

```text
quant_lab
legacy
compatibility
legacy_provider_adjusted
data_v3
V1
V2 compatibility
```

逐项人工判断。

理想情况下：

```text
quant_lab
```

作为 Python module/path/import 应该：

```text
0 个
```

注意：

仓库名：

```text
quant-lab
```

当然可以继续存在。

我们禁止的是代码 namespace：

```text
quant_lab
```

。

---

# 31. 最终源码结构不允许重复实现

最终不能出现：

```text
src/data/loader.py
src/xxx/data/loader.py
```

两套实现。

不能出现：

```text
旧 implementation
+
wrapper
+
新 implementation
```

每项能力只有：

> 一个 source of truth。

例如：

```text
Data Loader
→ src/data/loader.py

Chan
→ src/chan/

Strategy
→ src/strategies/

Backtest
→ src/backtest/
```

---

# 32. 不要为了“向后兼容”保留垃圾代码

本次任务明确授权：

```text
删除 obsolete code
删除 obsolete tests
删除 obsolete docs
删除 obsolete configs
```

不要采取之前的保守策略：

```text
“先留着，可能以后有人用”
```

没有这个要求。

原则：

> 当前没有使用、只服务旧 release 的代码就删。

---

# 33. 但是不要误删真正有用的新功能

这里的“大胆删除”不意味着随便删。

需要区别：

### 删除

```text
compat wrapper
legacy V1 loader
old import entry
old SPY special handling
old schema compatibility
旧测试
```

### 保留

```text
新的 Data Store
Manifest / SHA
Provider snapshot
Yahoo
Tushare
Local Provider
multi asset
multi timeframe
resample
market models
chan-core
strategy interface
backtest engine
execution abstraction
portfolio abstraction
metrics
future-mutation / no-lookahead
```

---

# 34. 不要重新设计 Data Layer

当前新的 Data Layer 已经开发完成。

本任务主要做：

```text
move
delete
rename
imports
tests
docs
```

除非清理 legacy 需要局部修改。

不要借机会重写：

```text
Store
Manifest
Provider
Normalizer
```

的核心行为。

---

# 35. 不要重新设计 Chan-Core

同样：

```text
src/quant_lab/chan/*
```

移动到：

```text
src/chan/*
```

即可。

不要借清理目录改：

```text
包含逻辑
分型规则
笔规则
confirmed/tentative
```

。

如果发现现有实现有明显 bug：

先记录。

不要混入本次纯结构清理，除非 bug 是路径迁移直接导致的。

---

# 36. Git 处理建议

因为 Git 能识别高相似度文件移动：

尽量使用：

```bash
git mv
```

例如：

```bash
git mv src/quant_lab/chan src/chan
git mv src/quant_lab/market src/market
```

对于：

```text
src/data
```

已经存在 compatibility wrapper 的情况：

先清理旧 wrapper，再把真正实现移动过来。

不要复制一份然后留原文件。

---

# 37. 推荐执行顺序

## Step 1：分析

先列出当前：

```text
src/
```

真实结构。

标记：

```text
REAL
WRAPPER
LEGACY
```

例如：

```text
src/quant_lab/chan       REAL
src/quant_lab/data       REAL

src/data/loader.py       WRAPPER
src/backtest.py          WRAPPER

legacy SPY path          LEGACY
```

---

## Step 2：移动新代码

执行概念上的：

```text
src/quant_lab/market      → src/market
src/quant_lab/data        → src/data
src/quant_lab/chan        → src/chan
src/quant_lab/strategies  → src/strategies
src/quant_lab/backtest    → src/backtest
```

处理：

```text
src/quant_lab/validation.py
```

到正确位置。

---

## Step 3：删除 wrapper

删除旧：

```text
src/backtest.py
src/strategy.py
src/execution.py
src/portfolio.py
src/metrics.py
src/data_loader.py
```

以及所有 compatibility redirect。

---

## Step 4：删除 legacy V1

删除：

```text
legacy loader
legacy price basis
legacy SPY regression
legacy API
legacy metadata handling
```

。

---

## Step 5：统一 imports

全仓：

```text
quant_lab.*
```

→

```text
src.*
```

。

---

## Step 6：重构 tests

合并：

```text
tests/data
tests/data_v3
```

。

删除 legacy tests。

---

## Step 7：更新 scripts/config/docs

确保实际路径一致。

---

## Step 8：全仓 grep

执行类似：

```bash
grep -R "quant_lab" .
grep -R "legacy_provider_adjusted" .
grep -R "Compatibility module" src tests scripts
grep -R "data_v3" .
```

确认没有残留。

排除：

```text
.git
缓存
构建产物
```

。

---

# 38. 验收标准

最终必须满足：

### 目录

```text
src/quant_lab
```

不存在。

---

### 正式目录

至少存在：

```text
src/data
src/market
src/chan
src/strategies
src/backtest
```

。

---

### 不存在旧单文件入口

不存在：

```text
src/backtest.py
src/strategy.py
src/execution.py
src/portfolio.py
src/metrics.py
src/data_loader.py
```

除非其中某个经过分析后确实是一个和 package 不冲突、且当前架构真正需要的独立模块。

默认应该删除。

---

### Import

业务代码不再出现：

```python
from quant_lab...
import quant_lab...
```

。

统一：

```python
from src...
```

。

---

### Compatibility wrapper

源码中不允许存在：

```python
sys.modules[__name__] = import_module(...)
```

这种旧路径跳转。

---

### Legacy

不存在：

```text
legacy_provider_adjusted
legacy_path
download_legacy
test_legacy_spy_regression
```

。

---

### Data tests

不存在：

```text
tests/data_v3
```

。

只有：

```text
tests/data
```

测试当前正式数据层。

---

### 功能

以下当前新功能仍然工作：

```text
multi asset
multi timeframe
Local Provider
Yahoo Provider
Tushare Provider
Data Store
Manifest
SHA verification
Resample
Market model
Chan combiner
Fractal
Stroke
ChanAnalyzer
Strategy interface
SMA strategy
Backtest engine
Execution
Portfolio
Metrics
No-lookahead
Prefix invariance
```

。

---

# 39. 测试原则发生变化

不要把：

```text
原来所有测试必须继续通过
```

作为目标。

正确目标是：

```text
所有仍然属于当前产品定义的测试必须通过。
```

旧版 compatibility test：

```text
应该删除
```

，而不是：

```text
为了测试继续保留旧代码。
```

最终：

```bash
python -m pytest -q
```

应该全部通过。

但测试集合应该已经被清理成：

```text
当前版本测试
```

，而不是：

```text
当前版本 + 历史包袱
```

。

---

# 40. README 的定位

README 第一段不要继续描述：

```text
V1
V2
兼容层
SPY legacy
```

。

README 应该直接描述当前项目是什么，例如：

```text
Quant Lab 是一个用于多资产、多周期量化研究的实验框架。

核心模块：
- data
- market
- chan
- strategies
- backtest
```

历史版本请通过 GitHub Release / tag 查看。

无需在 README 主体中继续维护旧架构教程。

---

# 41. AGENTS.md 同步

`AGENTS.md` 也必须修改。

Codex 后续看到的工程说明必须明确：

```text
源码直接位于 src/*
```

例如：

```text
src/data
src/chan
src/strategies
src/backtest
```

不要让以后新的 Codex 又根据旧说明重新创建：

```text
src/quant_lab
```

。

明确写：

> Do not create another project-name package under `src`.
> `src/` itself is the project source root.

---

# 42. 不要过度考虑 Python packaging 教科书规范

这次以：

```text
这个项目的可读性
用户明确要求
当前仓库实际使用方式
```

为优先。

不要因为：

```text
“src layout 通常应该 src/package_name”
```

而拒绝修改。

本项目明确选择：

```text
src/data
src/chan
src/backtest
...
```

这种扁平源码布局。

这是项目设计决定。

---

# 43. 最终请给出清理报告

完成后输出：

## Deleted

列出：

```text
删除的 compatibility 文件
删除的 legacy 文件
删除的 legacy tests
```

。

## Moved

列出：

```text
src/quant_lab/... → src/...
```

。

## Import changes

说明：

```text
quant_lab.* → src.*
```

。

## Tests

给出：

```text
pytest 总数
passed
failed
```

。

## Repository tree

最后给出新的：

```text
src/
```

目录树。

---

# 44. 最终原则

这次请不要采取：

```text
为了安全什么都保留
```

的策略。

我们已经有：

```text
Git history
Git tag
GitHub Release
```

保存旧版本。

`dev` 分支的任务是：

> 向前开发当前正确版本。

所以：

```text
旧代码不适用于当前架构
→ 删除

旧测试只验证废弃行为
→ 删除

旧 API 只是历史兼容
→ 删除

wrapper 只是为了旧 import
→ 删除
```

最终目标：

```text
一个功能
一个实现
一个路径
一个 source of truth
```

而不是：

```text
旧实现
+
compatibility wrapper
+
新实现
+
项目名套娃
```
