"""Draw existing Chan objects; never recompute fractals or stroke endpoints."""
from src.chan.enums import Direction, FractalType, StrokeStatus
from .styles import (RANGE_COLOR, TOP_COLOR, BOTTOM_COLOR, UP_STROKE, DOWN_STROKE,
                     ordered, new_figure, save_figure, no_data)
from .candles import draw_candles
import matplotlib.dates as mdates


def draw_merged_bars(ax, merged_bars, *, annotate=False):
    merged_bars = ordered(merged_bars, 'index')
    merged_bars = ordered(merged_bars, 'end_timestamp')
    if not merged_bars:
        no_data(ax)
        return
    times = mdates.date2num([bar.end_timestamp for bar in merged_bars])
    for time, bar in zip(times, merged_bars):
        ax.plot([time, time], [bar.low, bar.high], color=RANGE_COLOR, linewidth=1.4,
            marker='_', markersize=8, zorder=2)
        if annotate:
            ax.annotate(f'M{bar.index} raw{list(bar.raw_indices)}', (time, bar.low),
                xytext=(0, -14), textcoords='offset points', ha='center', fontsize=7)


def draw_fractals(ax, fractals, price_range):
    # Display offset only: stored fractal prices and stroke endpoints are unchanged.
    offset = max(price_range * .01, 1e-12)
    for fractal in fractals:
        top = fractal.type == FractalType.TOP
        ax.scatter(mdates.date2num(fractal.pivot_time), fractal.price + (offset if top else -offset),
            marker='v' if top else '^', color=TOP_COLOR if top else BOTTOM_COLOR,
            s=55, zorder=5, label='TOP pivot' if top else 'BOTTOM pivot')


def draw_strokes(ax, strokes):
    for stroke in strokes:
        confirmed = stroke.status == StrokeStatus.CONFIRMED
        up = stroke.direction == Direction.UP
        ax.plot(mdates.date2num([stroke.start.pivot_time, stroke.end.pivot_time]),
            [stroke.start.price, stroke.end.price], color=UP_STROKE if up else DOWN_STROKE,
            linestyle='-' if confirmed else '--', linewidth=1.8, zorder=4,
            label=f'{stroke.direction.value.upper()} {stroke.status.value.upper()}')


def plot_merged_bars(merged_bars, output_path, *, title=None, annotate=False):
    figure, ax = new_figure(title, 'Merged high-low ranges at end_timestamp | no open/close')
    draw_merged_bars(ax, merged_bars, annotate=annotate)
    return save_figure(figure, ax, output_path)


def plot_chan_structure(merged_bars, fractals, strokes, output_path, *, title=None):
    merged_bars = tuple(merged_bars)
    figure, ax = new_figure(title, 'Merged ranges + Chan structure | solid: confirmed; dashed: tentative',
        retrospective=True)
    draw_merged_bars(ax, merged_bars)
    price_range = max((bar.high for bar in merged_bars), default=0) - min(
        (bar.low for bar in merged_bars), default=0)
    draw_fractals(ax, fractals, price_range)
    draw_strokes(ax, strokes)
    return save_figure(figure, ax, output_path)


def plot_raw_with_chan_overlay(raw_bars, fractals, strokes, output_path, *, title=None):
    raw_bars = tuple(raw_bars)
    figure, ax = new_figure(title, 'Raw OHLC + Chan overlay | solid: confirmed; dashed: tentative',
        retrospective=True)
    draw_candles(ax, raw_bars)
    price_range = max((bar.high for bar in raw_bars), default=0) - min(
        (bar.low for bar in raw_bars), default=0)
    draw_fractals(ax, fractals, price_range)
    draw_strokes(ax, strokes)
    return save_figure(figure, ax, output_path)
