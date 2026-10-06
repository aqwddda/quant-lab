from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import subprocess
import sys
import pandas as pd
import pytest
from src.chan import ChanAnalyzer
from src.strategies.chan_fx import ChanFxStrategy
from src.strategies.base import StrategyContext
from src.data.inspection import write_chan_outputs
from src.data.store import DataStore
from src.market import Instrument
from src.validation import chan_future_mutation_test
from test_strokes import bars


def test_observer_has_no_orders_and_reset():
    strategy=ChanFxStrategy()
    history=bars([3,1,3,4,5,7,5,4,3,1,3])
    for i,bar in enumerate(history):
        assert strategy.on_bar(StrategyContext(i,bar.available_at),bar).target is None
    assert len(strategy.analyzer.strokes)==2
    strategy.reset()
    assert not strategy.analyzer.raw_bars
    with pytest.raises(NotImplementedError,match='rules'):
        ChanFxStrategy(observe_only=False)
    assert chan_future_mutation_test(history,history[5].available_at)


def test_inspection_cli(tmp_path):
    root=Path(__file__).resolve().parents[2]
    fixture=json.loads((root/'tests/fixtures/chan/alternating_strokes.json').read_text())
    frame=pd.DataFrame([{'timestamp':datetime(2020,1,1,tzinfo=timezone.utc)+timedelta(minutes=i),
        'symbol':'EURUSD','open':(high+low)/2,'high':high,'low':low,'close':(high+low)/2}
        for i,(high,low) in enumerate(fixture['raw_ranges'])])
    store=DataStore(tmp_path/'store')
    store.save_dataset(frame,dataset_id='chan_fixture',provider='local',provider_version='1',
        instruments=[Instrument('EURUSD','EURUSD.a','forex','fixture')],timeframe='1m',source_timezone='UTC',source_frames={'bars':frame})
    proc=subprocess.run([sys.executable,str(root/'scripts/inspect_chan.py'),'--dataset-id','chan_fixture',
        '--symbol','EURUSD','--root',str(store.root),'--output',str(tmp_path/'output'),'--plot'],capture_output=True,text=True)
    assert proc.returncode==0,proc.stderr
    report=json.loads((tmp_path/'output/chan.json').read_text())
    assert report['audit']['mode']=='structure_observation_only'
    assert len(report['strokes'])==3
    assert report['strokes'][-1]['status']=='tentative'
    for name in ['raw_bars.csv','merged_bars.csv','fractals.csv','strokes.csv','chan.json','chan.png']:
        assert (tmp_path/'output'/name).is_file()


def test_chan_core_has_no_dataframe_or_provider_imports():
    import ast
    folder=Path(__file__).resolve().parents[2]/'src/chan'
    for path in folder.glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            names = [a.name for a in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
            assert not any(name.split('.')[0] in {'pandas','numpy','yfinance','tushare','matplotlib'} or name.startswith('src.data') for name in names)


def test_chan_config_observer_cli(tmp_path):
    import yaml
    root=Path(__file__).resolve().parents[2]
    history=bars([3,1,3,4,5,7,5,4,3,1,3])
    frame=pd.DataFrame([{'timestamp':b.timestamp,'symbol':b.symbol,'open':b.open,
        'high':b.high,'low':b.low,'close':b.close} for b in history])
    store=DataStore(tmp_path/'store')
    store.save_dataset(frame,dataset_id='fx_observer',provider='local',provider_version='1',
        instruments=[Instrument('EURUSD','EURUSD.a','forex','fixture')],timeframe='1m',
        source_timezone='UTC',source_frames={'bars':frame})
    strategy=yaml.safe_load((root/'config/chan_fx.yaml').read_text())
    strategy['data']['timeframe']='1m'
    strategy_path=tmp_path/'strategy.yaml';strategy_path.write_text(yaml.safe_dump(strategy))
    config=yaml.safe_load((root/'config/backtest.yaml').read_text())
    config.update(start_date='2020-01-01',end_date='2020-01-01',reports_dir=str(tmp_path/'reports'))
    config_path=tmp_path/'backtest.yaml';config_path.write_text(yaml.safe_dump(config))
    command=[sys.executable,str(root/'scripts/run_backtest.py'),'--strategy-config',str(strategy_path),
        '--backtest-config',str(config_path),'--dataset-id','fx_observer','--data-root',str(store.root)]
    proc=subprocess.run(command+['--observe-only'],capture_output=True,text=True)
    assert proc.returncode==0,proc.stderr
    report=json.loads((tmp_path/'reports/chan_fx_observer/chan.json').read_text())
    assert report['audit']['mode']=='structure_observation_only'
    assert not (tmp_path/'reports/metrics.json').exists()
    proc=subprocess.run(command,capture_output=True,text=True)
    assert proc.returncode!=0
    assert 'undefined' in proc.stderr
