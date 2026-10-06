"""Compatibility module; use quant_lab.backtest.metrics."""
import sys
from importlib import import_module
sys.modules[__name__] = import_module("quant_lab.backtest.metrics")
