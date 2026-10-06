"""One completed raw bar advances only the affected structure tail."""
from .combiner import InclusionProcessor
from .fractal import FractalDetector
from .stroke import StrokeBuilder


class ChanAnalyzer:
    def __init__(self, config=None):
        self.inclusion = InclusionProcessor(config)
        self.detector = FractalDetector()
        self.builder = StrokeBuilder()
        self._raw_bars = []
        self._fractals = []

    @property
    def raw_bars(self):
        return tuple(self._raw_bars)

    @property
    def merged_bars(self):
        return self.inclusion.merged_bars

    @property
    def fractals(self):
        return tuple(self._fractals)

    @property
    def strokes(self):
        return self.builder.strokes

    @property
    def confirmed_strokes(self):
        return self.builder.confirmed_strokes

    @property
    def current_stroke(self):
        return self.builder.current_stroke

    def update(self, bar):
        appended = self.inclusion.update(bar)
        self._raw_bars.append(bar)
        if appended and len(self.inclusion.tail) == 3:
            fractal = self.detector.detect(*self.inclusion.tail)
            if fractal is not None:
                self.builder.update(fractal, self.inclusion._bars)
                self._fractals.append(fractal)
        return self

    def extend(self, bars):
        for bar in bars:
            self.update(bar)
        return self
