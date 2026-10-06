from datetime import datetime, timezone
import pandas as pd
import pytest
from quant_lab.market import AssetClass, Timeframe, Bar, Instrument
from quant_lab.data.store import DataStore
from quant_lab.data.loader import load_dataset
from quant_lab.data.validation import validate_bars_v3
from quant_lab.data.manifest import file_sha256


def frame(frequency='15min'):
    return pd.DataFrame({'timestamp': pd.date_range('2020-01-01', periods=4, freq=frequency, tz='UTC'),
        'symbol': ['EURUSD']*4, 'open': [1.1]*4, 'high': [1.2]*4,
        'low': [1.0]*4, 'close': [1.15]*4, 'tick_volume': [10]*4})


@pytest.mark.parametrize('value', ['1m','5m','15m','30m','1h','4h','1d'])
def test_timeframe(value):
    parsed = Timeframe.parse(value)
    assert Timeframe.parse(parsed) is parsed
    assert parsed.duration.total_seconds() > 0


def test_resample_compatibility():
    assert Timeframe.M1 < Timeframe.M15 < Timeframe.H4
    assert Timeframe.M5.can_resample_to('1h')
    assert not Timeframe.H1.can_resample_to('15m')
    with pytest.raises(ValueError): Timeframe.parse('2h')


@pytest.mark.parametrize('frequency,timeframe', [('min','1m'),('15min','15m'),('h','1h')])
def test_valid_v3_without_real_volume(frequency,timeframe):
    validate_bars_v3(frame(frequency), timeframe)
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
    with pytest.raises(ValueError): validate_bars_v3(data,'15m')


def test_v3_roundtrip_identity_and_immutability(tmp_path):
    store=DataStore(tmp_path)
    instrument=Instrument('EURUSD','EURUSD.a',AssetClass.FOREX,'broker_x',base_currency='EUR',quote_currency='USD')
    options=dict(dataset_id='fx_v1',provider='local',provider_version='1',instruments=[instrument],
        timeframe='15m',source_timezone='UTC',source_frames={'bars':frame()})
    manifest=store.save_bars_v3(frame(),**options)
    assert manifest['schema_version']==3
    assert '/forex/broker_x/15m/EURUSD/' in manifest['normalized_files']['bars']['path']
    assert manifest['instruments'][0]['provider_symbol']=='EURUSD.a'
    pd.testing.assert_frame_equal(load_dataset('fx_v1',store=store),frame())
    sha=file_sha256(store.manifest_path('fx_v1'))
    with pytest.raises(FileExistsError): store.save_bars_v3(frame(),**options)
    assert file_sha256(store.manifest_path('fx_v1'))==sha
    manifest['instruments'][0]['provider_symbol']='EURUSDm'
    with pytest.raises(ValueError,match='identity'): store.verify(manifest)


def test_v2_read_compatibility(tmp_path):
    store=DataStore(tmp_path)
    bars=frame('D').rename(columns={'timestamp':'date'}).drop(columns='tick_volume')
    bars['date']=pd.bdate_range('2020-01-01',periods=4).astype('datetime64[ns]')
    bars['volume']=1000
    store.save_dataset(bars,dataset_id='v2',provider='fixture',provider_version='1',
        market='US',asset_type='EQUITY',start='2020-01-01',end='2020-01-06',source_frames={'bars':bars})

    with pytest.raises(ValueError,match='session_timezone'):
        load_dataset('v2',store=store)
    adapted=load_dataset('v2',store=store,session_timezone='America/New_York')
    assert str(adapted.timestamp.dt.tz)=='UTC'
    assert adapted.timestamp.iloc[0]==pd.Timestamp('2020-01-01T05:00Z')
    assert store.load_manifest('v2')['schema_version']==2


def test_new_yahoo_snapshot_publishes_v3(tmp_path):
    from scripts.download_data import download_dataset_v3
    from quant_lab.data.providers.yahoo import YahooProvider
    from tests.data.test_yahoo_provider import FakeYahoo
    store=DataStore(tmp_path)
    manifest=download_dataset_v3('yahoo','AAPL','2020-08-28','2020-08-31',store=store,
        dataset_id='yahoo_v3',provider_instance=YahooProvider(client=FakeYahoo()))
    assert manifest['schema_version']==3
    data=load_dataset('yahoo_v3',store=store,price_basis='provider_adjusted')
    assert len(data)==2
    assert str(data.timestamp.dt.tz)=='UTC'
    assert manifest['instruments'][0]['asset_class']=='equity'


def test_provider_capabilities():
    from quant_lab.data.providers.yahoo import YahooProvider
    YahooProvider.capabilities.require('equity','1d')
    with pytest.raises(NotImplementedError):
        YahooProvider.capabilities.require('forex','15m')
