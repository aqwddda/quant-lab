"""Strict triple detector. Overlap is allowed; stroke selection is separate."""
from .enums import FractalType
from .models import Fractal


class FractalDetector:
    def detect(self, left, center, right):
        if not left.index + 1 == center.index == right.index - 1:
            raise ValueError('Fractal requires consecutive merged bars')
        if center.high > max(left.high, right.high) and center.low > max(left.low, right.low):
            kind, price = FractalType.TOP, center.high
        elif center.low < min(left.low, right.low) and center.high < min(left.high, right.high):
            kind, price = FractalType.BOTTOM, center.low
        else:
            # Provisional strict equality rule: equal high/low produces no fractal.
            return None
        # A center is sealed when a non-containing right bar appears. Subsequent
        # right inclusion continues its reversal direction, reinforcing this
        # strict inequality. Keep the as-known right snapshot, not a future edit.
        return Fractal(kind, left, center, right, center.end_timestamp, right.available_at, price)
