"""Structure observation only. Friend-specific trading rules are not defined."""
from src.chan import ChanAnalyzer, ChanConfig
from src.strategies.base import TargetPosition


class ChanFxStrategy:
    def __init__(self, config=None, *, observe_only=True):
        if not observe_only:
            raise NotImplementedError('Chan-FX trading rules have not been defined')
        self.config = config or ChanConfig()
        self.reset()

    def reset(self):
        self.analyzer = ChanAnalyzer(self.config)

    def on_bar(self, context, bar):
        if context.available_at != bar.available_at:
            raise ValueError('Observation context must match completed bar availability')
        self.analyzer.update(bar)
        return TargetPosition(None)  # Observations never become orders.
