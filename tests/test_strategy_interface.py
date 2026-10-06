from datetime import datetime, timedelta, timezone
import pickle
import pandas as pd
import pytest
from quant_lab.market import Bar, Timeframe
from quant_lab.strategies.base import TargetPosition
from quant_lab.strategies.sma import SmaCrossStrategy, calculate_signals
from quant_lab.backtest.engine import BacktestEngine
from quant_lab.backtest.execution import Costs, EquityCashExecutionModel, FxExecutionModel
from quant_lab.backtest.portfolio import EquityPortfolio
from quant_lab.backtest.metrics import calculate_metrics, daily_equity_snapshot


def raw(values):
    return [Bar(datetime(2020,1,1,tzinfo=timezone.utc)+timedelta(minutes=i),
        'AAPL',v,v+1,v-1,v,timeframe=Timeframe.M1) for i,v in enumerate(values)]


class ScriptedStrategy:
    def reset(self): self.i=0
    def on_bar(self,context,bar):
        target=[None,1,0,1][self.i]
        assert context.index==self.i
        assert context.available_at==bar.available_at
        self.i+=1
        return TargetPosition(target,{'custom_feature':bar.close*2})


def test_generic_engine_next_open_and_final_unexecuted():
    result=BacktestEngine(ScriptedStrategy(),EquityCashExecutionModel(Costs(0,0)),
        EquityPortfolio(1000)).run(raw([100,101,102,103]))
    assert result.trades.side.tolist()==['BUY','SELL']
    assert result.trades.execution_date.tolist()==[raw([100,101,102,103])[2].timestamp,raw([100,101,102,103])[3].timestamp]
    assert result.trades.custom_feature.tolist()==[202,204]
    assert 'fast_ma' not in result.equity
    assert result.equity.position_quantity.iloc[-1]==0


def test_sma_stream_exact_against_existing_pandas(bars):
    from quant_lab.strategies.base import StrategyContext
    expected=calculate_signals(bars,20,60)
    strategy=SmaCrossStrategy(20,60)
    observed=[]
    for i,b in enumerate(raw(bars.close.tolist())):
        decision=strategy.on_bar(StrategyContext(i,b.available_at),b)
        observed.append({**decision.diagnostics,'target':-1 if decision.target is None else decision.target})
    pd.testing.assert_frame_equal(pd.DataFrame(observed),expected,check_exact=True)


def test_daily_metrics_from_intraday_equity():
    equity=pd.DataFrame({'date':pd.to_datetime(['2020-01-01T10:00Z','2020-01-01T11:00Z','2020-01-02T10:00Z','2020-01-02T11:00Z']),
        'equity':[110.,120.,100.,90.],'daily_return':[.1,.09,-.16,-.1],
        'drawdown':[0.,0.,-.16,-.25],'position_quantity':[0]*4})
    daily=daily_equity_snapshot(equity,100)
    assert daily.equity.tolist()==[120,90]
    assert daily.daily_return.tolist()==pytest.approx([.2,-.25])
    from quant_lab.backtest.models import TRADE_COLUMNS
    trades=pd.DataFrame(columns=TRADE_COLUMNS)
    observed=calculate_metrics(equity,trades,100,252,0)
    expected=calculate_metrics(daily.drop(columns=[],errors='ignore'),trades,100,252,0)
    assert observed==expected
    assert observed['annualized_volatility']==pytest.approx(pd.Series([.2,-.25]).std()*252**.5)


def test_fx_execution_explicitly_unimplemented():
    with pytest.raises(NotImplementedError,match='spread'):
        FxExecutionModel()


def test_v3_intraday_cli_and_daily_metrics(tmp_path):
    import subprocess
    import sys
    import json
    import yaml
    from pathlib import Path
    from quant_lab.market import Instrument
    from quant_lab.data.store import DataStore
    from tests.data_v3.test_market import frame
    dates=pd.date_range('2020-01-01',periods=200,freq='15min',tz='UTC')
    bars=pd.DataFrame({'timestamp':dates,'symbol':['AAPL']*200,'open':[100.]*200,
        'high':[102.]*200,'low':[99.]*200,'close':[101.]*200,'volume':[100]*200})
    root=Path(__file__).resolve().parents[1]
    store=DataStore(tmp_path/'store')
    store.save_bars_v3(bars,dataset_id='intraday',provider='local',provider_version='1',
        instruments=[Instrument('AAPL','AAPL','equity','NASDAQ',quote_currency='USD')],
        timeframe='15m',source_timezone='UTC',source_frames={'bars':bars})
    strategy=tmp_path/'strategy.yaml'
    strategy.write_text(yaml.safe_dump({'strategy':{'name':'sma_cross','params':{'fast_window':2,'slow_window':3}},
        'data':{'symbol':'AAPL','asset_class':'equity','venue':'NASDAQ','timeframe':'15m','price_basis':'raw'}}))
    config=yaml.safe_load((root/'config/backtest.yaml').read_text())
    config.update(start_date='2020-01-01',end_date='2020-01-03',reports_dir=str(tmp_path/'reports'))
    backtest=tmp_path/'backtest.yaml';backtest.write_text(yaml.safe_dump(config))
    proc=subprocess.run([sys.executable,str(root/'scripts/run_backtest.py'),'--strategy-config',str(strategy),
        '--backtest-config',str(backtest),'--dataset-id','intraday','--data-root',str(store.root)],capture_output=True,text=True)
    assert proc.returncode==0,proc.stderr
    report=json.loads((tmp_path/'reports/metrics.json').read_text())
    assert report['audit']['metrics_frequency']=='daily'
    assert report['audit']['timeframe']=='15m'
    assert report['audit']['future_mutation_test_passed']
    assert len(pd.read_csv(tmp_path/'reports/equity.csv'))==200


def test_engine_has_no_strategy_specific_imports():
    import ast
    from pathlib import Path
    path=Path(__file__).resolve().parents[1]/'src/quant_lab/backtest/engine.py'
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node,ast.ImportFrom):
            assert node.module not in {'quant_lab.strategies.sma','quant_lab.chan','quant_lab.strategies.chan_fx'}
