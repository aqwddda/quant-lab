import pandas as pd
import pytest
from src.data.resample import resample_bars, resample_dataset
from src.data.store import DataStore
from src.market import Instrument


def minutes(start='2020-01-01T00:00Z',count=240,freq='min'):
    dates=pd.date_range(start,periods=count,freq=freq)
    prices=[1+i/1000 for i in range(count)]
    return pd.DataFrame({'timestamp':dates,'symbol':['EURUSD']*count,'open':prices,
        'high':[x+.02 for x in prices],'low':[x-.02 for x in prices],
        'close':[x+.01 for x in prices],'tick_volume':[2]*count,
        'amount':[10.]*count,'open_interest':range(count)})


@pytest.mark.parametrize('source,target,freq,count', [('1m','5m','min',240),('1m','15m','min',240),
    ('1m','1h','min',240),('1m','4h','min',240),('5m','1h','5min',48),('1h','4h','h',4)])
def test_resample_ohlc_optional(source,target,freq,count):
    data=minutes(count=count,freq=freq)
    result=resample_bars(data,source_timeframe=source,target_timeframe=target,aggregation_timezone='UTC',anchor='00:00')
    n=count//len(result)
    assert result.open.iloc[0]==data.open.iloc[0]
    assert result.high.iloc[0]==data.high.iloc[:n].max()
    assert result.low.iloc[0]==data.low.iloc[:n].min()
    assert result.close.iloc[0]==data.close.iloc[n-1]
    assert result.tick_volume.iloc[0]==2*n
    assert result.amount.iloc[0]==10*n
    assert result.open_interest.iloc[0]==n-1
    assert 'volume' not in result
    assert result.available_at.iloc[0]>result.timestamp.iloc[0]


def test_anchor_and_timezone_change_windows():
    a=resample_bars(minutes(),source_timeframe='1m',target_timeframe='4h',aggregation_timezone='UTC',anchor='00:00')
    b=resample_bars(minutes(start='2020-01-01T01:00Z'),source_timeframe='1m',target_timeframe='4h',aggregation_timezone='UTC',anchor='01:00')
    assert a.timestamp.iloc[0]!=b.timestamp.iloc[0]
    c=resample_bars(minutes(start='2020-01-01T00:30Z',count=60),source_timeframe='1m',target_timeframe='1h',aggregation_timezone='Asia/Kolkata',anchor='00:00')
    assert c.timestamp.iloc[0]==pd.Timestamp('2020-01-01T00:30Z')


@pytest.mark.parametrize('problem',['missing','partial','duplicate','unsorted'])
def test_no_silent_repair(problem):
    data=minutes()
    if problem=='missing': data=data.drop(index=10)
    elif problem=='partial': data=data.iloc[:-1]
    elif problem=='duplicate': data.loc[1,'timestamp']=data.timestamp.iloc[0]
    else:data=data.iloc[::-1]
    with pytest.raises(ValueError):
        resample_bars(data,source_timeframe='1m',target_timeframe='4h',aggregation_timezone='UTC',anchor='00:00')


def test_resampled_frozen_lineage(tmp_path):
    store=DataStore(tmp_path)
    parent=store.save_dataset(minutes(),dataset_id='source',provider='local',provider_version='1',
        instruments=[Instrument('EURUSD','EURUSDm','forex','broker_x')],timeframe='1m',source_timezone='UTC',source_frames={'bars':minutes()})
    manifest=resample_dataset('source',target_timeframe='4h',aggregation_timezone='UTC',anchor='00:00',dataset_id='fourhour',store=store)
    assert manifest['lineage']['source_dataset_id']=='source'
    assert manifest['lineage']['source_normalized_sha256']==parent['normalized_sha256']
    assert manifest['anchor']=='00:00'
    assert store.load_manifest('source')==parent
    assert len(store.verify(manifest)['bars'])==1


def test_lineage_metadata_is_validated(tmp_path):
    from src.data.manifest import validate_manifest
    store=DataStore(tmp_path)
    store.save_dataset(minutes(),dataset_id='source',provider='local',provider_version='1',
        instruments=[Instrument('EURUSD','EURUSD','forex','fixture')],timeframe='1m',source_timezone='UTC',source_frames={'bars':minutes()})
    manifest=resample_dataset('source',target_timeframe='4h',aggregation_timezone='UTC',anchor='00:00',dataset_id='target',store=store)
    manifest['lineage']['anchor']='01:00'
    with pytest.raises(ValueError,match='lineage metadata'):
        validate_manifest(manifest)
