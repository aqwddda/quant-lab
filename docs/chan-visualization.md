# Chan 可视化与人工核对

这套工具使用本地冻结数据和已有 Chan 对象，输出静态 PNG、CSV、JSON。
绘图不重算分型或笔，不改变算法状态，不生成订单或 Forex 收益。

## 一次生成全部输出

```bash
conda activate quant-lab
python scripts/inspect_chan.py --dataset-id <dataset_id> --symbol EURUSD \
  --start 2026-01-01T00:00:00Z --end 2026-01-10T00:00:00Z \
  --output reports/chan_case_001 --plot
```

也可以显式指定 Manifest：

```bash
python scripts/inspect_chan.py --manifest /path/to/store/data/manifests/<id>.json \
  --root /path/to/store --symbol EURUSD --output reports/chan_case_001 --plot
```

`--dataset-id` 与 `--manifest` 必须且只能指定一个。`--root` 是 Manifest 内相对文件路径的存储根目录，默认项目根目录。
两种入口均先核验 Manifest、identity 和文件 SHA，再筛选 symbol 与时间范围，最后逐根调用 `ChanAnalyzer.update()`。
时间边界须带时区，按 bar-start timestamp 闭区间筛选；范围起点是 cold start，不隐含此前历史。
初始包含仍按当前规则报错；可用已有 `--initial-direction-policy up/down` 显式指定实验默认值。
不加 `--plot` 时仍导出结构数据及摘要，但不生成新图片。

## 输出与含义

| 文件 | 内容 |
| --- | --- |
| `01_raw_candles.png` | 原始 OHLC：high-low wick、open-close body；上涨绿色、下跌红色，open=close 画 doji 横线 |
| `02_merged_bars.png` | 包含处理后的 high-low range，横轴为 end_timestamp |
| `03_chan_structure.png` | Merged range + TOP/BOTTOM 分型 + 笔 |
| `04_raw_with_chan_overlay.png` | 原始 K 线上叠加同一组分型和笔，供 TradingView/MT5 对照 |
| `raw_bars.csv` | OHLC、UTC timestamp、symbol、timeframe、available_at 与可选成交量字段 |
| `merged_bars.csv` | 区间、起止时间、available_at、raw_indices、raw_count、direction |
| `fractals.csv` | 左中右 merged index、原始索引、high/low，以及 pivot_time、price、confirmed_at |
| `strokes.csv` | 起终点 index、pivot_time、price、direction、status、formed_at、confirmed_at |
| `chan.json` | 相同结构的 JSON 及 dataset/Manifest、分析窗口与初始方向审计信息 |
| `05_summary.txt` | symbol、timeframe、各结构数量、confirmed 笔数、是否存在 tentative 笔 |

MergedBar 没有 open/close，它表达算法处理后的价格区间，不能画成红绿 OHLC candle。
绘图只使用 high/low，不能拿原始开收盘或区间中点补出虚构的 merged candle。

TOP 使用向下三角 `▼`，位于已有分型价格上方；BOTTOM 使用向上三角 `▲`，位于价格下方。
显示偏移为当前图价格范围的 1%，只影响 marker，不改变导出的价格或笔端点。
笔的 UP 为蓝色，DOWN 为橙色；**confirmed 实线，tentative 虚线**。最后一笔的 tentative 状态保持原样。

## 时间与状态

原始 K 使用 `Bar.timestamp`，merged 使用 `end_timestamp`，分型和笔端点直接使用已有对象的 `pivot_time` 与 `price`。
三种位置共用 UTC 时间坐标，不通过 OHLC 再猜分型位置，不压缩实际时间间隔。

图是选定窗口分析完成后的结构快照。marker 画在 pivot_time，**不表示该时刻已经知道分型**。
分型实际已知时间为 confirmed_at；笔的 formed_at 与 confirmed_at 见 CSV/JSON。
例如某个底在 00:01，但 00:03 才确认，marker 仍画在 00:01，不能据此模拟 00:01 成交。
用于回测的决策必须依赖已知时间，绘图不提供新的交易规则。

## 人工核对顺序

1. 使用 `01_raw_candles.png` 核对同一 symbol、周期、时区、窗口与 OHLC 数据。
2. 使用 `02_merged_bars.png` 和 merged CSV 的 raw_indices/raw_count 核对包含范围。
3. 使用 `03_chan_structure.png` 和 fractals CSV 的左中右 high/low 核对顶底判断。
4. 使用 `04_raw_with_chan_overlay.png` 核对笔的端点和状态，再查看对应确认时间。

请先区分原始数据、包含、分型和笔规则的差异。工具不会自动修复数据或改选端点；现有 invariant 错误仍会直接报错。
静态图不会截断输入或自动分页，大窗口可能拥挤，建议显式缩小 start/end。改变窗口也会改变 cold-start 状态，需要保留审计信息。
图上的合成 fixture 数据只用于工程检查，不能作为真实行情证据。

## Python API

```python
from src.data.loader import load_dataset, iter_bars
from src.chan import ChanAnalyzer
from src.data.inspection import write_chan_outputs
from src.visualization import plot_merged_bars

frame = load_dataset('explicit_id', symbols=['EURUSD'])
analyzer = ChanAnalyzer()
for bar in iter_bars(frame):
    analyzer.update(bar)
write_chan_outputs(analyzer, 'reports/chan_case', plot=True)
plot_merged_bars(analyzer.merged_bars, 'reports/chan_case/debug_merged.png', annotate=True)
```

`annotate=True` 显示 M index 和对应 raw_indices，时间仍由 UTC 横轴保留。
四个正式绘图函数见 `src/visualization/`，均为只读函数；空结构也能生成图，乱序输入报错。
`write_chan_outputs` 默认导出 CSV/JSON，可用 `export_csv=False` 或 `export_json=False` 控制；摘要独立输出。
Chan-Core 不依赖绘图库，可视化使用已有 matplotlib，不需要 GUI 或额外依赖。
