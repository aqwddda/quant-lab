# Quant Lab Chan 可视化与调试模块开发方案

仓库：

https://github.com/aqwddda/quant-lab

目标分支：

```text
dev
```

请直接基于当前最新 `dev` 分支开发。

本轮目标是在**不修改 Chan-Core 算法行为**的前提下，补齐一套正式的 Chan 可视化与调试工具链。

---

# 1. 当前背景

当前 `chan-core` 已经可以产出：

```text
raw_bars
merged_bars
fractals
strokes
confirmed_strokes
current_stroke
```

当前系统已经具备：

```text
原始 OHLC Bar
    ↓
包含处理
    ↓
MergedBar
    ↓
顶分型 / 底分型
    ↓
Stroke
```

但是现在的图形能力还不够。

当前 inspection 主要输出：

```text
raw_bars.csv
merged_bars.csv
fractals.csv
strokes.csv
chan.json
```

以及一张较粗糙的：

```text
raw close 折线 + stroke 连线
```

这不足以直接和 TradingView / MT5 上的 K 线结构做人工对照。

本轮要补齐真正可用的：

```text
原始 K 线图
处理包含后的结构图
顶底分型图
最终笔图
原始 K + Chan Overlay 对照图
```

---

# 2. 本轮最终目标

给定一个 dataset，例如：

```text
EURUSD
15m
某个时间区间
```

运行一次 inspection 后，至少输出：

```text
raw_bars.csv
merged_bars.csv
fractals.csv
strokes.csv
chan.json

01_raw_candles.png
02_merged_bars.png
03_chan_structure.png
04_raw_with_chan_overlay.png
```

如果实现方便，可以额外输出：

```text
05_summary.txt
```

内容包括：

```text
symbol
timeframe
raw bar count
merged bar count
fractal count
stroke count
confirmed stroke count
whether tentative stroke exists
```

---

# 3. 本轮明确不做的内容

不要修改：

```text
Chan-Core 算法规则
包含规则
初始方向规则
严格顶底分型规则
笔距离规则
同类极值替换规则
tentative / confirmed
Stroke extreme invariant
bar overlap validation
```

不要实现：

```text
线段
中枢
背驰
买卖点
Chan-FX 最终交易策略
Forex execution
short
lot
leverage
margin
spread
swap
```

本轮只做：

```text
可视化
inspection
debug export
```

---

# 4. 架构原则

## 4.1 Chan-Core 保持纯算法

以下目录继续保持纯算法：

```text
src/chan/
```

不要让 `src/chan/` import：

```text
matplotlib
pandas plotting
mplfinance
plotly
streamlit
GUI library
```

Chan-Core 只负责生成结构。

## 4.2 可视化单独成模块

建议新增：

```text
src/visualization/
├── __init__.py
├── candles.py
├── chan.py
└── styles.py
```

职责：

```text
candles.py
    → 原始 OHLC K 线图

chan.py
    → merged bar
    → fractal
    → stroke
    → overlay

styles.py
    → 图形样式
    → marker
    → line style
    → size
    → color
```

如果认为 `styles.py` 没必要，可以不拆。

原则是：

> 不要把 matplotlib 逻辑继续堆进 `src/data/inspection.py`。

---

# 5. inspection 层职责

当前：

```text
src/data/inspection.py
```

已经负责导出 Chan 结构数据。

本轮建议继续保留这个职责：

```text
analyzer
    ↓
flatten
    ↓
CSV / JSON
    ↓
调用 visualization
```

不要让它承担大量绘图细节。

最终大致：

```python
write_chan_outputs(
    analyzer,
    output,
    *,
    audit=None,
    export_csv=True,
    export_json=True,
    plot=False,
)
```

如果：

```python
plot=True
```

则调用：

```text
src.visualization
```

生成图。

---

# 6. 图一：01_raw_candles.png

用途：

> 展示原始市场 OHLC 数据。

要求使用：

```text
Bar.open
Bar.high
Bar.low
Bar.close
```

画标准 candlestick。

至少包含：

```text
wick
body
time axis
price axis
```

建议：

```text
上涨 K：绿色
下跌 K：红色
```

这张图应该尽量接近 TradingView / MT5 里看到的普通 K 线。

可选 title：

```text
EURUSD | 15m | 2026-01-01 → 2026-01-10
```

如果能拿到 dataset_id，也可以加入。

---

# 7. 原始 K 线不要依赖 mplfinance

优先使用：

```text
matplotlib
```

自行绘制。

每根 K：

```text
high-low
→ 竖线

open-close
→ rectangle
```

不要新增 `mplfinance`，除非有充分理由。

当前项目已有 matplotlib，可以直接复用。

---

# 8. 图二：02_merged_bars.png

用途：

> 展示包含处理之后真正参与分型判断的 K 结构。

这里必须特别注意：

```text
MergedBar
```

不是原始市场 OHLC K 线。

当前 MergedBar 有：

```text
index
high
low
start_timestamp
end_timestamp
available_at
raw_bars
raw_indices
direction
```

但是没有：

```text
open
close
```

因此：

> 不允许为了图像好看伪造 merged open/close。

不要把它画成传统红绿 candle。

---

# 9. MergedBar 的正确画法

建议画成：

```text
High-Low Range Bar
```

例如：

```text
     high
      ─
      │
      │
      │
      ─
     low
```

每一个 merged bar：

```text
x = merged bar index 或时间
top = high
bottom = low
```

如果希望更容易 debug，可以：

```text
M0
M1
M2
...
```

标在每根 bar 下方。

可选 debug 模式：

```text
M3 ← raw[5,6,7]
```

但不要让默认图过于拥挤。

---

# 10. MergedBar 时间轴

优先让 merged 图仍然保留时间意义。

建议：

```text
x 使用 end_timestamp 或 center/pivot 所在时间
```

而不是只画：

```text
0,1,2,3,4
```

但 merged index 仍然可以作为辅助标记。

如果使用时间轴实现过于复杂，可以：

- 主 X 使用 merged index
- secondary annotation 标时间

但不要丢失时间信息。

---

# 11. 图三：03_chan_structure.png

用途：

> 直接查看完整 Chan 结构。

底图：

```text
MergedBar
```

叠加：

```text
Top Fractal
Bottom Fractal
Stroke
```

这是最重要的一张结构图。

---

# 12. 顶分型标记

顶分型：

```text
TOP
```

marker 画在：

```text
center bar high 上方
```

推荐：

```text
▼
```

或者：

```text
downward triangle
```

marker 不要遮住 bar。

可以使用一个动态 offset：

```text
offset = 当前可见价格范围 * 1%
```

---

# 13. 底分型标记

底分型：

```text
BOTTOM
```

marker 画在：

```text
center bar low 下方
```

推荐：

```text
▲
```

或者：

```text
upward triangle
```

同样使用动态 offset。

---

# 14. Fractal 信息必须来源于现有对象

不要重新推导 fractal。

直接使用：

```text
Fractal.type
Fractal.center
Fractal.pivot_time
Fractal.price
Fractal.confirmed_at
```

绘图层不能重复实现分型算法。

---

# 15. Stroke 绘制

Stroke 直接使用：

```text
start
end
direction
status
confirmed_at
```

绘制连接线。

起点：

```text
start.pivot_time
start.price
```

终点：

```text
end.pivot_time
end.price
```

---

# 16. Confirmed / Tentative 视觉区别

必须明确区分。

建议：

```text
CONFIRMED
→ 实线

TENTATIVE
→ 虚线
```

例如：

```text
confirmed:
──────────

tentative:
- - - - - -
```

这样当前最后一笔是否已经确认可以直接看出来。

---

# 17. Stroke 方向

如果实现简单，可以：

```text
UP
→ 蓝色

DOWN
→ 橙色
```

如果希望整体视觉更简单，也可以统一颜色。

核心要求不是颜色，而是：

```text
confirmed / tentative
```

必须清楚。

---

# 18. 图四：04_raw_with_chan_overlay.png

用途：

> 直接和朋友的 TradingView / MT5 图进行对照。

底图使用：

```text
原始 candlestick
```

然后叠加：

```text
最终 fractal
stroke
```

这张图是人工校验最重要的一张。

---

# 19. 为什么 Overlay 很重要

假设朋友说：

```text
这里应该是一个顶分型
这里这一笔应该从 A 到 B
```

程序图可以直接放在同一段原始 K 上进行比较。

这样可以快速判断问题属于：

```text
原始数据不同
```

还是：

```text
包含处理不同
```

还是：

```text
分型判断不同
```

还是：

```text
笔构造规则不同
```

避免只看 JSON 猜。

---

# 20. Overlay 映射方式

Fractal / MergedBar 已经保留：

```text
raw_indices
pivot_time
price
```

因此 visualization 层应该基于已有字段映射回原始 K 图。

不要重新根据 OHLC 猜测 fractal 所在位置。

优先使用：

```text
pivot_time
```

定位。

必要时可以使用：

```text
center.raw_indices
```

做 debug annotation。

---

# 21. CSV 输出：raw_bars.csv

至少包含：

```text
timestamp
symbol
open
high
low
close
timeframe
volume
tick_volume
amount
open_interest
available_at
```

不存在的可选字段允许为空。

---

# 22. CSV 输出：merged_bars.csv

至少包含：

```text
index
high
low
start_timestamp
end_timestamp
available_at
raw_indices
direction
```

建议增加：

```text
raw_count
```

即：

```text
len(raw_indices)
```

方便快速查看哪些 merged bar 来自多个原始 K。

---

# 23. CSV 输出：fractals.csv

至少包含：

```text
type
left_index
center_index
right_index
pivot_time
confirmed_at
price

left_raw_indices
center_raw_indices
right_raw_indices

left_high
left_low
center_high
center_low
right_high
right_low
```

这样可以直接人工判断：

```text
为什么它是顶
为什么它是底
```

---

# 24. CSV 输出：strokes.csv

至少包含：

```text
start_index
end_index
start_pivot_time
end_pivot_time
start_price
end_price
direction
status
formed_at
confirmed_at
```

如果实现简单可以增加：

```text
is_confirmed
```

但不是必须。

---

# 25. chan.json

继续保留完整 JSON。

作用：

```text
inspection
notebook
future frontend
debug
```

不要删除。

---

# 26. CLI

继续增强：

```text
scripts/inspect_chan.py
```

期望支持：

```bash
python scripts/inspect_chan.py   --dataset-id <dataset_id>   --symbol EURUSD   --start 2026-01-01T00:00:00Z   --end 2026-01-10T00:00:00Z   --output reports/chan_case_001   --plot
```

也支持：

```bash
python scripts/inspect_chan.py   --manifest <manifest_path>   --symbol EURUSD   --plot
```

---

# 27. CLI 参数

至少保留：

```text
--dataset-id
--manifest
--symbol
--start
--end
--output
--plot
```

如果当前已有参数命名可以沿用。

不要为了本轮一次性增加十几个复杂 flag。

---

# 28. CLI 执行流程

完整流程应该是：

```text
1. Load dataset
2. Verify dataset
3. Filter symbol
4. Filter time range
5. Convert DataFrame → Bar
6. Feed ChanAnalyzer incrementally
7. Export CSV
8. Export JSON
9. Generate plots
```

不要绕过：

```text
ChanAnalyzer.update()
```

直接全量重算。

---

# 29. 推荐 Visualization API

```python
plot_raw_candles(
    bars,
    output_path,
    *,
    title=None,
)
```

```python
plot_merged_bars(
    merged_bars,
    output_path,
    *,
    title=None,
    annotate=False,
)
```

```python
plot_chan_structure(
    merged_bars,
    fractals,
    strokes,
    output_path,
    *,
    title=None,
)
```

```python
plot_raw_with_chan_overlay(
    raw_bars,
    fractals,
    strokes,
    output_path,
    *,
    title=None,
)
```

API 可以根据实际代码风格微调。

不要做复杂 class hierarchy。

---

# 30. Visualization 不应修改数据

所有绘图函数必须是：

```text
read-only
```

不要：

```text
sort
fill
deduplicate
repair
mutate analyzer
mutate Bar
mutate Fractal
mutate Stroke
```

如果输入顺序错误：

```text
raise
```

或者依赖上游已经验证的数据。

---

# 31. 图片命名固定

默认输出：

```text
01_raw_candles.png
02_merged_bars.png
03_chan_structure.png
04_raw_with_chan_overlay.png
```

不要随机命名。

---

# 32. 图片标题建议

每张图至少尽量包含：

```text
symbol
timeframe
start
end
```

Chan 图可增加：

```text
fractal count
stroke count
confirmed count
```

不要把大量 audit 信息全部塞在 title。

---

# 33. 大量 K 线问题

如果用户一次选：

```text
10000 bars
```

静态图会不可读。

本轮不需要自动做复杂分页。

可以：

- 正常生成
- 或提供合理 warning
- 或限制 inspection 推荐窗口

不要 silent 截断，除非用户显式传：

```text
--max-bars
```

---

# 34. Plot 的时间正确性

图上的 fractal：

```text
画在 pivot_time
```

但不要让图造成“当时已经知道”的错觉。

如果有 annotation，可以显示：

```text
pivot_time
confirmed_at
```

尤其 debug 模式下建议支持。

---

# 35. Tentative 状态必须保留

最后一笔：

```text
TENTATIVE
```

不要为了图看起来完整而自动当成 confirmed。

必须保持算法原始状态。

---

# 36. 当前 inspection.py 处理

当前 `write_chan_outputs(...)` 中已经有简单 matplotlib 逻辑。

本轮应：

```text
移除具体 plot implementation
```

改为调用：

```text
src.visualization
```

但 CSV / JSON flatten 逻辑可以继续保留。

不要为了“纯洁”把 inspection 重写一遍。

---

# 37. Tests

本轮必须补测试，但不要做 pixel-level golden image。

## Visualization Smoke Test

调用：

```text
plot_raw_candles
plot_merged_bars
plot_chan_structure
plot_raw_with_chan_overlay
```

确认：

```text
文件存在
文件大小 > 0
没有异常
```

即可。

## Inspection Integration Test

调用：

```text
write_chan_outputs(..., plot=True)
```

检查：

```text
raw_bars.csv
merged_bars.csv
fractals.csv
strokes.csv
chan.json
01_raw_candles.png
02_merged_bars.png
03_chan_structure.png
04_raw_with_chan_overlay.png
```

全部存在。

## CLI Integration Test

如果当前已有：

```text
tests/chan/test_integration.py
```

可以扩展已有 inspect CLI 测试。

运行：

```text
scripts/inspect_chan.py
```

确认：

```text
return code = 0
```

并生成全部预期文件。

---

# 38. 不要测试图像像素值

不要做：

```text
PNG binary exact hash
pixel-level screenshot comparison
```

matplotlib 版本变化会导致不稳定。

只需要：

```text
生成成功
基础结构正确
```

---

# 39. 文档

新增：

```text
docs/chan-visualization.md
```

说明：

```text
四张图分别是什么
MergedBar 为什么不是 candle
Top / Bottom marker 含义
Confirmed / Tentative 线型
CLI 使用方法
如何用于人工规则核对
```

README 只需要增加入口链接和简单示例。

---

# 40. 不要新增 GUI

本轮不要做：

```text
Streamlit
Dash
Qt
Web frontend
Browser app
```

PNG 已足够完成当前规则校验目标。

---

# 41. 不要新增 Plotly

当前项目已有：

```text
matplotlib
```

本轮优先使用现有依赖。

不要为了 hover / zoom 提前引入：

```text
plotly
bokeh
altair
```

后续如果确实需要交互分析再做。

---

# 42. 推荐开发顺序

## Phase 1

建立：

```text
src/visualization/
```

把当前 inspection plot 逻辑迁出去。

## Phase 2

实现：

```text
plot_raw_candles
```

确保能画标准 K 线。

## Phase 3

实现：

```text
plot_merged_bars
```

只使用：

```text
high / low
```

不伪造 OHLC。

## Phase 4

实现：

```text
plot_chan_structure
```

叠加：

```text
MergedBar
Fractal
Stroke
```

## Phase 5

实现：

```text
plot_raw_with_chan_overlay
```

用于真实图对照。

## Phase 6

整合：

```text
write_chan_outputs
scripts/inspect_chan.py
```

一键输出全部文件。

## Phase 7

补：

```text
tests
docs
README
```

---

# 43. 最终验收标准

必须满足：

```text
[1] 可以生成标准 raw candlestick
[2] 可以生成 merged high-low range bars
[3] merged bar 不伪造 open/close
[4] 可以在 merged 图上标 TOP/BOTTOM
[5] 可以连接 strokes
[6] confirmed stroke = 实线
[7] tentative stroke = 虚线
[8] 可以在 raw candlestick 上 overlay Chan structure
[9] CSV / JSON 继续正常输出
[10] CLI 可以一次生成全部输出
[11] Chan-Core 完全不依赖 visualization
[12] Chan-Core 行为没有修改
[13] bar overlap validation 没有修改
[14] Forex execution 没有修改
[15] pytest 全部通过
```

---

# 44. 最终输出目录示例

```text
reports/
└── chan_eurusd_case_001/
    ├── raw_bars.csv
    ├── merged_bars.csv
    ├── fractals.csv
    ├── strokes.csv
    ├── chan.json
    ├── 01_raw_candles.png
    ├── 02_merged_bars.png
    ├── 03_chan_structure.png
    └── 04_raw_with_chan_overlay.png
```

---

# 45. 最终开发报告

完成后请输出：

## Added

列出新增：

```text
src/visualization/*
docs/chan-visualization.md
相关 tests
```

## Changed

说明修改：

```text
src/data/inspection.py
scripts/inspect_chan.py
README.md
```

## Unchanged

明确确认未修改：

```text
Chan-Core behavior
Fractal rules
Stroke rules
bar overlap validation
Forex execution
Chan trading rules
```

## Test Result

给出：

```text
passed
failed
```

## Example Command

给出一个真实运行例子：

```bash
python scripts/inspect_chan.py ...
```

以及生成的文件列表。

---

# 46. 最终原则

本轮不是为了让图“花哨”。

优先级：

```text
正确表达结构
>
方便 debug
>
方便和朋友手工图核对
>
视觉美观
```

这套可视化主要服务两个场景：

```text
1. 自己 debug Chan-Core
2. 和朋友逐段对照真实外汇 K 线
```

不要为了视觉效果引入新的理论假设，也不要让 visualization 反向影响算法结果。
