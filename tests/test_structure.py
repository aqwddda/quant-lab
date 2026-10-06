"""Keep source ownership and public import paths explicit."""
import importlib
from pathlib import Path
import tomllib

ROOT=Path(__file__).resolve().parents[1]


def test_source_root_contains_only_current_modules():
    source=ROOT/'src'
    assert {p.name for p in source.glob('*.py')}=={'__init__.py','validation.py'}
    assert {p.name for p in source.iterdir() if p.is_dir() and p.name!='__pycache__'}=={
        'market','data','chan','strategies','backtest','visualization'}


def test_modules_have_their_actual_import_names():
    for name in ['src.data.loader','src.data.manifest','src.data.store','src.chan',
        'src.market','src.strategies.sma','src.backtest.engine','src.validation','src.visualization']:
        assert importlib.import_module(name).__name__==name


def test_packaging_discovers_the_source_root():
    project=tomllib.loads((ROOT/'pyproject.toml').read_text())
    assert project['tool']['setuptools']['packages']['find']=={'where':['.'],'include':['src*']}
