"""Compatibility module; use quant_lab.validation."""
import sys
from importlib import import_module
sys.modules[__name__] = import_module("quant_lab.validation")
