# Chan-Core：本项目的规则与状态边界

本轮只实现包含处理、合并 K、顶底分型和笔。规则来源是本轮方案；JSON Golden Fixtures 是人工标注，测试不以其它 Chan 库的输出作正确性 oracle。

## 1. 原始 Bar 的时序

`ChanAnalyzer.update(bar)` 接收一根已完成 Bar，`extend(bars)` 内部仍逐根调用。
一个 Analyzer 只处理一个 symbol/Timeframe；UTC 时间必须递增且前一 bar 已完成，不能重叠。
算法核心不导入 pandas、SDK 或绘图库。Caller 用 `data.loader.iter_bars` 做转换。

## 2. High/Low 方向

后 high 与 low 均严格升高为 UP，均严格降低为 DOWN。Open/Close 和 K 线颜色不参与方向判断。
包含时使用此前最近已确定的方向。

## 3. 包含关系

A.high≥B.high 且 A.low≤B.low，或反过来，均包含。
UP 合并 high=max、low=max；DOWN 合并 high=min、low=min。
每次用最新合并区间判断下一根原始 K，不能退回比较最后一根原始 K。
MergedBar 保存起止坐标、完成时间、原始 Bar 与 raw_indices、合并方向，历史对象为不可变快照。

## 4. 初始包含

没有已确定方向时默认 ERROR，停止并要求调用者选择初始策略；不猜测方向。
`ChanConfig(initial_direction_policy='up'/'down')` 是显式临时选择，必须记录于实验审计；不宣称是已确认理论。

## 5. 严格三 K 分型

只检查相邻的合并 K `(left, center, right)`。
TOP 要求 center.high 严格高于两侧 high，center.low 也严格高于两侧 low。
BOTTOM 要求 center.low 严格低于两侧 low，center.high 也严格低于两侧 high。
等高或等低不成分型，这是本期严格默认，仍待朋友确认。
允许相邻三 K 窗口重叠；是否能成笔由 StrokeBuilder 判断。

## 6. Pivot 与 confirmed_at

pivot_time 使用 center 合并 K 的结束 bar-start 坐标，price 是 center high（顶）或 low（底）。它不是策略可交易时间，也不声称对应内部 raw 极值首次出现的精确时刻。
confirmed_at 是右侧第一根有效 bar 的完成时间。中心 K 此时已经封闭；严格顶的右侧方向必然 DOWN，严格底的右侧方向必然 UP。
后续右侧包含沿该方向合并会强化既有严格比较，因此分型事件可以确认。事件冻结当时的 left/center/right 快照，不将后来追加的 right lineage 改写为当时可见。
检查脚本同时输出这些 as-known high/low 与 raw_indices，最终 merged_bars 表的右侧尾部可能继续演变。

## 7. 成笔与距离

BOTTOM→TOP 为 UP 笔，TOP→BOTTOM 为 DOWN 笔。
两端分型中心的合并索引差至少 4，意味着两个三 K 分型之间至少有一根独立合并 K。
计数单位是合并 K，不是 raw K；缺口不增加虚构的距离。

## 8. 同类端点延伸

尚未形成反向有效笔前，更高 TOP 替换 UP 笔的 tentative 结束端，更低 BOTTOM 对称替换 DOWN 笔结束端；不会新增一笔。
较低 TOP、较高 BOTTOM 忽略；相等保留第一次端点，是临时默认。
第一笔尚未形成时，同类型的更极端初始分型同样更新待选起点。
距离不足的反向分型不生成笔，原始分型事件仍保留。

## 9. 区间极值 invariant

UP 笔起底必须等于整个端点中心区间的最低 low，止顶必须等于该区间最高 high；DOWN 对称。
每次形成/延伸候选笔显式检查。违反时抛 ValueError，不静默移动其它端点或借其它流派规则修补。该失败需要查看分型选择与业务规则，调用者应停止当前分析并保留输入。
本期未追加“两个分型价格必须完全分离”等关系限制。

## 10. Tentative / Confirmed

A→B 最初 TENTATIVE；有效 B→C 出现时 A→B 变 CONFIRMED，confirmed_at 为 C 分型确认时间，B→C 是新的 TENTATIVE。
最终一笔通常未确认。confirmed 笔仅追加，不回写；已返回的 tentative 对象也不原地改变，而是返回新快照。
`raw_bars, merged_bars, fractals, strokes, confirmed_strokes` 返回 tuple，`current_stroke` 返回不可变对象或 None。
不提供 segment、zone、divergence、buy/sell point、多级联立或最后一根虚构分型。

## 11. 因果性测试

对前缀先记录确认事件，扩展到 1000 根后，原 confirmed fractals/strokes 必须相同。最后 tentative 可以继续延伸或确认。
未来变异比较 `confirmed_at <= cutoff`，不能用 pivot_time 判断当时已知。验证还覆盖右侧包含后 as-known 分型快照保持不变。
Golden：

- `tests/fixtures/chan/alternating_strokes.json`：中心 1/5/9/13 的往返笔与确认时点。
- `tests/fixtures/chan/sequential_inclusion.json`：连续包含后相对合并区间的方向与重叠分型。

## 12. 观察、导出与断点

```bash
python scripts/inspect_chan.py --dataset-id <id> --symbol EURUSD \
  --start 2020-01-01T00:00:00Z --end 2020-01-31T23:59:59Z --plot
```

默认输出 `reports/chan_<id>/raw_bars.csv, merged_bars.csv, fractals.csv, strokes.csv, chan.json` 与摘要，`--plot` 增加四张标准 PNG，详见 [Chan 可视化](chan-visualization.md)。无订单或收益报告。
初始包含报错时可以显式加 `--initial-direction-policy up/down` 作临时实验。
start/end 先选择分析范围，因此是 cold start，没有隐含先前历史。要检查全历史状态，应从版本起点分析。

```python
from src.chan import ChanAnalyzer
from src.data.loader import load_dataset, iter_bars

analyzer = ChanAnalyzer()
for bar in iter_bars(load_dataset('explicit_id')):
    analyzer.update(bar)
    current = analyzer.current_stroke
```

工程参考只取对象/管理器分离、尾部增量和确定/未确定状态边界；不复制其选笔、等值、gap 或虚笔规则：
[Combiner](https://github.com/Vespa314/chan.py/blob/main/Combiner/KLine_Combiner.py)、[KLine List](https://github.com/Vespa314/chan.py/blob/main/KLine/KLine_List.py)、[Bi / BiList](https://github.com/Vespa314/chan.py/blob/main/Bi/BiList.py)。

## 13. 待确认清单

| 问题 | 本期行为 |
| --- | --- |
| 初始包含方向 | 默认 ERROR；显式 UP/DOWN 可实验 |
| 分型等高/等低 | 严格比较，不成分型 |
| 同类端点等价 | 严格更极端才替换；相等保留第一次 |
| 缺口是否改变成笔距离 | 不改变，按合并 K 计数 |
| 成笔是否还有额外价格关系 | 不加；保留区间极值 invariant |
| 线段、中枢、背驰与最终买卖规则 | 本轮不实现，等待朋友规则 |
| 精确 raw 极值时刻与多级别结构 | 当前 pivot 是 merged-end 坐标；本轮不扩展 |

`ChanFxStrategy` 只推进 Analyzer、返回 `TargetPosition(None)`。启用实际交易会明确 NotImplemented；不能把观察结果解释为一个已经验证的 FX 策略。
