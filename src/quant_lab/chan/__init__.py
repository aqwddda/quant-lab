"""Pure incremental structure algorithms; no data transport or trading."""
from .config import ChanConfig
from .enums import Direction, FractalType, InitialDirectionPolicy, StrokeStatus
from .models import MergedBar, Fractal, Stroke
from .combiner import InclusionProcessor
from .fractal import FractalDetector
from .stroke import StrokeBuilder
from .analyzer import ChanAnalyzer
