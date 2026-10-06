from copy import deepcopy
from dataclasses import replace
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import pytest
from src.visualization import (plot_raw_candles, plot_merged_bars,
    plot_chan_structure, plot_raw_with_chan_overlay)
from src.visualization.candles import draw_candles
from src.visualization.chan import draw_merged_bars, draw_fractals, draw_strokes
from src.visualization.styles import UP_CANDLE, DOWN_CANDLE
from src.market import Timeframe


def snapshot(analyzer):
    return deepcopy((analyzer.raw_bars, analyzer.merged_bars, analyzer.fractals,
        analyzer.strokes, analyzer.confirmed_strokes, analyzer.current_stroke))


@pytest.mark.parametrize('empty', [False, True])
def test_all_four_plots_generate_files_without_mutation(analyzer, tmp_path, empty):
    if empty:
        from src.chan import ChanAnalyzer
        analyzer = ChanAnalyzer()
    before = snapshot(analyzer)
    plot_raw_candles(analyzer.raw_bars, tmp_path/'raw.png', title='EURUSD | 1m')
    plot_merged_bars(analyzer.merged_bars, tmp_path/'merged.png', annotate=True)
    plot_chan_structure(analyzer.merged_bars, analyzer.fractals, analyzer.strokes, tmp_path/'structure.png')
    plot_raw_with_chan_overlay(analyzer.raw_bars, analyzer.fractals, analyzer.strokes, tmp_path/'overlay.png')
    for name in ['raw.png', 'merged.png', 'structure.png', 'overlay.png']:
        assert (tmp_path/name).stat().st_size > 0
    assert snapshot(analyzer) == before


def test_candle_geometry_and_doji_use_actual_ohlc(analyzer):
    from matplotlib.colors import to_rgba
    ax = Figure().subplots()
    bars = list(analyzer.raw_bars[:3])
    bars[2] = replace(bars[2], close=bars[2].open)
    draw_candles(ax, bars)
    assert len(ax.patches) == 3
    for bar, body, color in zip(bars, ax.patches, [DOWN_CANDLE, UP_CANDLE, UP_CANDLE]):
        from matplotlib.patches import Rectangle
        assert isinstance(body, Rectangle)
        assert body.get_y() == min(bar.open, bar.close)
        assert body.get_height() == abs(bar.close-bar.open)
        assert body.get_facecolor() == to_rgba(color)
        assert body.get_width() == pytest.approx(bar.timeframe.duration.total_seconds()/86400*.7)
        assert body.get_x()+body.get_width()/2 == pytest.approx(mdates.date2num(bar.timestamp))
    for collection, bar in zip(ax.collections[:3], bars):
        assert collection.get_segments()[0][:, 1].tolist() == [bar.low, bar.high]
    doji_line = ax.collections[-1]
    assert doji_line.get_segments()[0][:, 1].tolist() == [bars[2].open]*2
    assert doji_line.get_segments()[0][1, 0]-doji_line.get_segments()[0][0, 0] == pytest.approx(
        bars[2].timeframe.duration.total_seconds()/86400*.7)
    assert doji_line.get_linewidths()[0] >= 2


@pytest.mark.parametrize('timeframe', list(Timeframe))
@pytest.mark.parametrize('count', [1, 3])
def test_candle_width_uses_declared_duration_despite_time_gaps(analyzer, timeframe, count):
    bars = [replace(bar, timestamp=analyzer.raw_bars[0].timestamp+i*timeframe.duration*5,
        timeframe=timeframe) for i, bar in enumerate(analyzer.raw_bars[:count])]
    ax = Figure().subplots()
    draw_candles(ax, bars)
    assert len(ax.patches) == count
    expected_width = timeframe.duration.total_seconds()/86400*.7
    for bar, body in zip(bars, ax.patches):
        assert body.get_width() == pytest.approx(expected_width)
        assert body.get_x()+body.get_width()/2 == pytest.approx(mdates.date2num(bar.timestamp))


def test_merged_ranges_do_not_fabricate_candle_bodies(analyzer):
    ax = Figure().subplots()
    draw_merged_bars(ax, analyzer.merged_bars, annotate=True)
    assert not ax.patches
    assert len(ax.lines) == len(analyzer.merged_bars)
    for bar, line in zip(analyzer.merged_bars, ax.lines):
        assert line.get_xdata().tolist() == [mdates.date2num(bar.end_timestamp)]*2
        assert line.get_ydata().tolist() == [bar.low, bar.high]
    assert ax.texts[0].get_text() == 'M0 raw[0]'


def test_pivots_and_stroke_status_come_from_existing_objects(analyzer):
    ax = Figure().subplots()
    draw_fractals(ax, analyzer.fractals, 8)
    for fractal, marker in zip(analyzer.fractals, ax.collections):
        x, y = marker.get_offsets()[0]
        assert x == mdates.date2num(fractal.pivot_time)
        assert y == pytest.approx(fractal.price + (.08 if fractal.type.value == 'top' else -.08))
    draw_strokes(ax, analyzer.strokes)
    assert [line.get_linestyle() for line in ax.lines] == ['-', '-', '--']
    for stroke, line in zip(analyzer.strokes, ax.lines):
        assert line.get_xdata().tolist() == mdates.date2num([stroke.start.pivot_time, stroke.end.pivot_time]).tolist()
        assert line.get_ydata().tolist() == [stroke.start.price, stroke.end.price]


@pytest.mark.parametrize('kind', ['raw', 'merged'])
def test_unordered_inputs_are_rejected(analyzer, tmp_path, kind):
    if kind == 'raw':
        function, data = plot_raw_candles, analyzer.raw_bars
    else:
        function, data = plot_merged_bars, analyzer.merged_bars
    with pytest.raises(ValueError, match='strictly increasing'):
        function(data[::-1], tmp_path/'invalid.png')
    assert not (tmp_path/'invalid.png').exists()
