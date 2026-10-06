"""Shared static plotting setup; no GUI backend or new data interpretation."""
from datetime import timezone
from pathlib import Path
import os

os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[2] / '.cache/matplotlib'))

import matplotlib.dates as mdates
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

UP_CANDLE = '#089981'
DOWN_CANDLE = '#f23645'
RANGE_COLOR = '#64748b'
TOP_COLOR = '#b91c1c'
BOTTOM_COLOR = '#15803d'
UP_STROKE = '#2563eb'
DOWN_STROKE = '#ea580c'


def ordered(items, attribute):
    """Reject unordered inputs; never sort, repair or mutate structures."""
    items = tuple(items)
    if any(getattr(left, attribute) >= getattr(right, attribute)
           for left, right in zip(items, items[1:])):
        raise ValueError(f'{attribute} must be strictly increasing')
    return items


def new_figure(title, description, *, retrospective=False):
    figure = Figure(figsize=(14, 6), layout='constrained')
    FigureCanvasAgg(figure)
    ax = figure.subplots()
    figure.suptitle(title or description, fontsize=12)
    if retrospective:
        description += '\nRetrospective pivots; known only at confirmed_at (see CSV/JSON)'
    ax.set_title(description, fontsize=9)
    ax.set(xlabel='UTC time (bar start / merged end / pivot)', ylabel='Price')
    locator = mdates.AutoDateLocator(tz=timezone.utc)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator, tz=timezone.utc))
    ax.grid(alpha=.2)
    ax.margins(x=.03, y=.12)
    return figure, ax


def save_figure(figure, ax, output_path):
    handles, labels = ax.get_legend_handles_labels()
    if labels:
        unique = dict(zip(labels, handles))
        ax.legend(unique.values(), unique.keys(), fontsize=8)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        figure.savefig(output_path, dpi=150)
    finally:
        figure.clear()
    return output_path


def no_data(ax):
    ax.text(.5, .5, 'No structures in this range', transform=ax.transAxes,
            ha='center', va='center', color=RANGE_COLOR)
