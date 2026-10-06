import subprocess
import sys
from pathlib import Path
import pandas as pd
import pytest
from src.market import Instrument, AssetClass, Timeframe
from src.data.store import DataStore
from src.data.loader import load_dataset
from scripts.download_data import import_local_dataset


@pytest.mark.parametrize('extension', ['csv','parquet'])
@pytest.mark.parametrize('symbol,vendor,timeframe,freq', [('EURUSD','EURUSD.a','15m','15min'),('GBPUSD','GBPUSDm','1h','h')])
def test_local_frozen_pipeline(tmp_path,extension,symbol,vendor,timeframe,freq):
    source=pd.DataFrame({'timestamp':pd.date_range('2020-01-01',periods=8,freq=freq),
        'symbol':[vendor]*8,'open':[1.1]*8,'high':[1.2]*8,'low':[1.0]*8,'close':[1.15]*8,'tick_volume':[42]*8})
    path=tmp_path/f'{symbol}.{extension}'
    if extension=='csv': source.to_csv(path,index=False)
    else: source.to_parquet(path,index=False)
    original=path.read_bytes()
    store=DataStore(tmp_path/'store')
    instrument=Instrument(symbol,vendor,AssetClass.FOREX,'broker_x')
    options=dict(instrument=instrument,timeframe=timeframe,source_timezone='Asia/Shanghai',
        timestamp_semantics='bar_end',store=store,dataset_id=symbol+'_snapshot')
    manifest=import_local_dataset(path,**options)
    loaded=load_dataset(manifest['dataset_id'],store=store)
    assert 'volume' not in loaded
    assert loaded.tick_volume.eq(42).all()
    assert loaded.symbol.eq(symbol).all()
    assert loaded.timestamp.iloc[0] == pd.Timestamp('2020-01-01',tz='Asia/Shanghai').tz_convert('UTC')-pd.Timedelta(timeframe)
    assert store.resolve(manifest['source_files']['original']['path']).read_bytes()==original
    path.unlink()
    assert len(load_dataset(manifest['dataset_id'],store=store))==8
    with pytest.raises(FileExistsError): import_local_dataset(path,**options)
    root=Path(__file__).resolve().parents[2]
    for script in ['verify_dataset.py','inspect_data.py']:
        proc=subprocess.run([sys.executable,str(root/'scripts'/script),'--root',str(store.root),
            '--dataset-id',manifest['dataset_id']],capture_output=True,text=True)
        assert proc.returncode==0,proc.stderr


def test_local_failure_preserves_source(tmp_path):
    path=tmp_path/'bad.csv'
    path.write_text('timestamp,open,high,low,close\n2020-01-01,1,0.5,0.8,1\n')
    store=DataStore(tmp_path/'store')
    with pytest.raises(ValueError,match='Impossible'):
        import_local_dataset(path,instrument=Instrument('EURUSD','EURUSD','forex','fixture'),timeframe='1m',
            source_timezone='UTC',timestamp_semantics='bar_start',store=store,dataset_id='bad')
    assert store.resolve('data/source/local/bad/original.bin').read_bytes()==path.read_bytes()
    assert not store.manifest_path('bad').exists()


def test_aware_source_offsets_match_declared_zone(tmp_path):
    path=tmp_path/'offset.csv'
    path.write_text('timestamp,open,high,low,close\n2020-01-01T00:00:00+08:00,1,1.2,0.8,1\n')
    with pytest.raises(ValueError,match='source_timezone'):
        import_local_dataset(path,instrument=Instrument('EURUSD','EURUSD','forex','fixture'),
            timeframe='1m',source_timezone='UTC',timestamp_semantics='bar_start',
            store=DataStore(tmp_path/'store'),dataset_id='wrong_zone')


@pytest.mark.parametrize('timeframe', list(Timeframe))
@pytest.mark.parametrize('instrument', [
    Instrument('AAPL', 'AAPL.vendor', AssetClass.EQUITY, 'NASDAQ',
        quote_currency='USD', tick_size=.01, lot_size=1),
    Instrument('EURUSD', 'EURUSD.a', AssetClass.FOREX, 'broker_x',
        base_currency='EUR', quote_currency='USD', tick_size=.00001,
        lot_size=100000, contract_multiplier=100000),
    Instrument('ESZ26', 'ESZ6', AssetClass.FUTURES, 'CME',
        quote_currency='USD', tick_size=.25, lot_size=1,
        contract_multiplier=50, expiry='2026-12-18'),
])
def test_all_assets_and_timeframes_preserve_canonical_instrument(tmp_path, instrument, timeframe):
    from dataclasses import asdict, fields, FrozenInstanceError
    import json
    from src.data.providers.local import LocalBarProvider
    LocalBarProvider.capabilities.require(instrument.asset_class, timeframe)
    path = tmp_path / 'bars.csv'
    source = pd.DataFrame({'timestamp': pd.date_range('2020-01-01', periods=3, freq=timeframe.duration),
        'symbol': [instrument.provider_symbol]*3,
        'open': [10.]*3, 'high': [11.]*3, 'low': [9.]*3, 'close': [10.5]*3})
    source.to_csv(path, index=False)
    store = DataStore(tmp_path / 'store')
    manifest = import_local_dataset(path, instrument=instrument, timeframe=timeframe,
        source_timezone='UTC', timestamp_semantics='bar_start', store=store, dataset_id='snapshot')
    published = store.load_manifest('snapshot')
    metadata = published['instruments'][0]
    assert set(metadata) == {field.name for field in fields(Instrument)} == {
        'symbol', 'provider_symbol', 'asset_class', 'venue', 'base_currency', 'quote_currency',
        'tick_size', 'lot_size', 'contract_multiplier', 'expiry'}
    assert metadata == {**asdict(instrument), 'asset_class': instrument.asset_class.value}
    assert Instrument(**metadata) == instrument
    assert instrument.provider_symbol != instrument.symbol
    with pytest.raises(FrozenInstanceError):
        instrument.venue = 'changed'
    request = json.loads(store.resolve(manifest['source_files']['request']['path']).read_text())
    assert request['instrument'] == metadata
    assert manifest['timeframe'] == timeframe.value
    assert set(manifest['normalized_files']) == {'bars'}
    assert not store.resolve('data/normalized/instruments').exists()
    loaded = load_dataset('snapshot', store=store)
    assert loaded.symbol.eq(instrument.symbol).all()
    assert loaded.timestamp.diff().dropna().eq(timeframe.duration).all()
    assert store.resolve(manifest['source_files']['original']['path']).read_bytes() == path.read_bytes()
