"""Close-only indicators; targets become available after the row's close."""
from collections import deque
from src.strategies.base import TargetPosition


class _RollingMean:
    """Bounded streaming sum with separate add/remove compensation.

    Preserves the installed pandas rolling-mean arithmetic, including constant
    runs. Tests compare streamed values exactly against pandas.
    """
    def __init__(self, window):
        self.window = window
        self.values = deque()
        self.total = self.add_compensation = self.remove_compensation = 0.0
        self.previous = None
        self.same_count = 0

    def update(self, value):
        value = float(value)
        if len(self.values) == self.window:
            old = self.values.popleft()
            y = -old - self.remove_compensation
            total = self.total + y
            self.remove_compensation = (total - self.total) - y
            self.total = total
        if not self.values:
            self.total = self.add_compensation = self.remove_compensation = 0.0
            self.same_count = 0
        y = value - self.add_compensation
        total = self.total + y
        self.add_compensation = (total - self.total) - y
        self.total = total
        self.same_count = self.same_count + 1 if value == self.previous else 1
        self.previous = value
        self.values.append(value)
        if len(self.values) < self.window:
            return float('nan')
        return value if self.same_count >= self.window else self.total / self.window


class SmaCrossStrategy:
    def __init__(self, fast_window=20, slow_window=60):
        if (type(fast_window) is not int or type(slow_window) is not int
                or not 0 < fast_window < slow_window):
            raise ValueError('Require integer windows: 0 < fast_window < slow_window')
        self.fast_window, self.slow_window = fast_window, slow_window
        self.reset()

    def reset(self):
        self._fast = _RollingMean(self.fast_window)
        self._slow = _RollingMean(self.slow_window)

    def on_bar(self, context, bar):
        import math
        fast, slow = self._fast.update(bar.close), self._slow.update(bar.close)
        target = None if math.isnan(slow) else int(fast > slow)
        return TargetPosition(target, {'fast_ma': fast, 'slow_ma': slow})
