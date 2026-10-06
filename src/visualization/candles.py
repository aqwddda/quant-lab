"""Standard OHLC candles, drawn directly from immutable market Bars."""
from .styles import UP_CANDLE, DOWN_CANDLE, ordered, new_figure, save_figure, no_data
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle


def draw_candles(ax, bars):
    bars = ordered(bars, 'timestamp')
    if not bars:
        no_data(ax)
        return
    if len({bar.symbol for bar in bars}) != 1 or len({bar.timeframe for bar in bars}) != 1:
        raise ValueError('Candle view requires one symbol and timeframe')
    times = mdates.date2num([bar.timestamp for bar in bars])
    # Matplotlib datetime units are days. Session gaps never widen a candle.
    width = bars[0].timeframe.duration.total_seconds() / 86400 * .7
    for time, bar in zip(times, bars):
        color = UP_CANDLE if bar.close >= bar.open else DOWN_CANDLE
        ax.vlines(time, bar.low, bar.high, color=color, linewidth=1, zorder=2)
        ax.add_patch(Rectangle((time-width/2, min(bar.open, bar.close)), width,
            abs(bar.close-bar.open), facecolor=color, edgecolor=color, linewidth=.9, zorder=3))
        # A true doji has zero price height. Emphasize its body at the exact price,
        # without inventing an open/close difference or changing the stored OHLC.
        if bar.close == bar.open:
            ax.hlines(bar.open, time-width/2, time+width/2, color=color, linewidth=2.2, zorder=3)
    ax.autoscale_view()


def plot_raw_candles(bars, output_path, *, title=None):
    figure, ax = new_figure(title, 'Raw OHLC candles | green: close >= open; red: close < open')
    draw_candles(ax, bars)
    return save_figure(figure, ax, output_path)
