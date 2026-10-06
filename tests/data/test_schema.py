from datetime import datetime, timezone
import pandas as pd
import pytest
from src.market import AssetClass, Timeframe, Bar, Instrument
from src.data.store import DataStore
from src.data.loader import load_dataset
from src.data.validation import validate_bars
from src.data.manifest import file_sha256


def frame(frequency='15min'):
    return pd.DataFrame({'timestamp': pd.date_range('2020-01-01', periods=4, freq=frequency, tz='UTC'),
        'symbol': ['EURUSD']*4, 'open': [1.1]*4, 'high': [1.2]*4,
        'low': [1.0]*4, 'close': [1.15]*4, 'tick_volume': [10]*4})


@pytest.mark.parametrize('value', ['1m','5m','15m','30m','1h','4h','1d'])
def test_timeframe(value):
    parsed = Timeframe.parse(value)
    assert Timeframe.parse(parsed) is parsed
    assert parsed.duration.total_seconds() > 0


def test_resample_timeframe_relation():
    assert Timeframe.M1 < Timeframe.M15 < Timeframe.H4
    assert Timeframe.M5.can_resample_to('1h')
    assert not Timeframe.H1.can_resample_to('15m')
    with pytest.raises(ValueError): Timeframe.parse('2h')


@pytest.mark.parametrize('frequency,timeframe', [('min','1m'),('15min','15m'),('h','1h')])
def test_optional_real_volume(frequency,timeframe):
    validate_bars(frame(frequency), timeframe)
    bar=Bar(datetime(2020,1,1,tzinfo=timezone.utc),'EURUSD',1.1,1.2,1.,1.15,timeframe=Timeframe.parse(timeframe))
    assert bar.volume is None
    assert bar.available_at > bar.timestamp


@pytest.mark.parametrize('problem', ['naive','timezone','duplicate','unsorted','ohlc','missing','negative','fractional_ticks'])
def test_reject_dirty(problem):
    data=frame()
    if problem=='naive': data['timestamp']=data.timestamp.dt.tz_localize(None)
    elif problem=='timezone': data['timestamp']=data.timestamp.dt.tz_convert('Asia/Shanghai')
    elif problem=='duplicate': data.loc[1,'timestamp']=data.timestamp.iloc[0]
    elif problem=='unsorted': data=data.iloc[::-1]
    elif problem=='ohlc': data.loc[0,'high']=1.05
    elif problem=='missing': data.loc[0,'close']=float('nan')
    elif problem=='negative': data.loc[0,'tick_volume']=-1
    else: data['tick_volume']=0.5
    with pytest.raises(ValueError): validate_bars(data,'15m')


def test_roundtrip_identity_and_immutability(tmp_path):
    store=DataStore(tmp_path)
    instrument=Instrument('EURUSD','EURUSD.a',AssetClass.FOREX,'broker_x',base_currency='EUR',quote_currency='USD')
    options=dict(dataset_id='fx_snapshot',provider='local',provider_version='1',instruments=[instrument],
        timeframe='15m',source_timezone='UTC',source_frames={'bars':frame()})
    manifest=store.save_dataset(frame(),**options)
    assert manifest['schema_version']==3
    assert '/forex/broker_x/15m/EURUSD/' in manifest['normalized_files']['bars']['path']
    assert manifest['instruments'][0]['provider_symbol']=='EURUSD.a'
    pd.testing.assert_frame_equal(load_dataset('fx_snapshot',store=store),frame())
    sha=file_sha256(store.manifest_path('fx_snapshot'))
    with pytest.raises(FileExistsError): store.save_dataset(frame(),**options)
    assert file_sha256(store.manifest_path('fx_snapshot'))==sha
    manifest['instruments'][0]['provider_symbol']='EURUSDm'
    with pytest.raises(ValueError,match='identity'): store.verify(manifest)


def test_yahoo_snapshot_publishes_current_schema(tmp_path):
    from scripts.download_data import download_dataset
    from src.data.providers.yahoo import YahooProvider
    from tests.data.test_yahoo_provider import FakeYahoo
    store=DataStore(tmp_path)
    manifest=download_dataset('yahoo','AAPL','2020-08-28','2020-08-31',store=store,
        dataset_id='yahoo_snapshot',provider_instance=YahooProvider(client=FakeYahoo()))
    assert manifest['schema_version']==3
    data=load_dataset('yahoo_snapshot',store=store,price_basis='provider_adjusted')
    assert len(data)==2
    assert str(data.timestamp.dt.tz)=='UTC'
    assert manifest['instruments'][0]['asset_class']=='equity'


def test_provider_capabilities():
    from src.data.providers.yahoo import YahooProvider
    YahooProvider.capabilities.require('equity','1d')
    with pytest.raises(NotImplementedError):
        YahooProvider.capabilities.require('forex','15m')


def test_qfq_anchor_uses_selected_request_end(tmp_path):
    store=DataStore(tmp_path)
    dates=pd.bdate_range('2020-01-01',periods=3).astype('datetime64[ns]')
    bars=pd.DataFrame({'date':dates,'symbol':['000001.SZ']*3,'open':[10.]*3,'high':[11.]*3,
        'low':[9.]*3,'close':[10.]*3,'volume':[1000]*3})
    adjustments=pd.DataFrame({'date':dates,'symbol':['000001.SZ']*3,'adj_factor':[1.,2.,4.],
        'provider':['fixture']*3,'factor_semantics':['cumulative_adjustment_factor']*3})
    bars['timestamp']=bars.date.dt.tz_localize('Asia/Shanghai').dt.tz_convert('UTC')
    store.save_dataset(bars,dataset_id='anchor',provider='fixture',provider_version='1',
        instruments=[Instrument('000001.SZ','000001.SZ','equity','SZSE')],timeframe='1d',
        source_timezone='Asia/Shanghai',session_timezone='Asia/Shanghai',
        source_frames={'bars':bars},normalized_frames={'adjustments':adjustments})
    selected=load_dataset('anchor',store=store,
        end='2020-01-02T23:59:59+08:00',price_basis='qfq')
    assert selected.close.tolist()==[5.,10.]


def test_optional_available_at_cannot_claim_earlier_or_later_close():
    data=frame()
    data['available_at']=data.timestamp+pd.Timedelta(minutes=16)
    with pytest.raises(ValueError,match='fixed bar end'):
        validate_bars(data,'15m')


def test_multi_symbol_and_futures_metadata(tmp_path):
    store=DataStore(tmp_path)
    first=frame().drop(columns='tick_volume')
    first['symbol']='ESZ26'
    first['open_interest']=1234
    second=first.copy();second['symbol']='ESH27'
    data=pd.concat([first,second],ignore_index=True).sort_values(['timestamp','symbol']).reset_index(drop=True)
    manifest=store.save_dataset(data,dataset_id='futures_reference',provider='local',provider_version='1',
        instruments=[Instrument('ESZ26','ESZ6','futures','CME',tick_size=.25,contract_multiplier=50,expiry='2026-12-18'),
            Instrument('ESH27','ESH7','futures','CME',tick_size=.25,contract_multiplier=50,expiry='2027-03-19')],
        timeframe='15m',source_timezone='UTC',source_frames={'bars':data})
    assert len(load_dataset('futures_reference',store=store))==8
    assert load_dataset('futures_reference',symbols=['ESZ26'],store=store).symbol.eq('ESZ26').all()
    assert manifest['instruments'][0]['contract_multiplier']==50
