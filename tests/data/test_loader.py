import pandas as pd
import pytest
from src.data.loader import load_dataset
from src.market import Instrument


def test_single_symbol_range(store,saved,canonical):
    loaded=load_dataset(saved['dataset_id'],symbols=['AAPL'],start='2020-01-08T00:00Z',end='2020-01-15T00:00Z',store=store)
    expected=canonical.loc[canonical.timestamp.between('2020-01-08T00:00Z','2020-01-15T00:00Z')].reset_index(drop=True)
    pd.testing.assert_frame_equal(loaded,expected)
    assert loaded.attrs['manifests'][0]['dataset_id']==saved['dataset_id']


def test_multi_symbol_long_format(store,canonical,dataset_options):
    other=canonical.copy();other['symbol']='MSFT'
    combined=pd.concat([canonical,other]).sort_values(['timestamp','symbol']).reset_index(drop=True)
    options={**dataset_options,'instruments':[Instrument('AAPL','AAPL','equity','NASDAQ'),Instrument('MSFT','MSFT','equity','NASDAQ')]}
    manifest=store.save_dataset(combined,dataset_id='multi_symbol',source_frames={'bars':combined},**options)
    loaded=load_dataset(manifest['dataset_id'],store=store)
    assert len(loaded)==len(canonical)*2
    assert not loaded.duplicated(['timestamp','symbol']).any()
    assert loaded.symbol.iloc[:4].tolist()==['AAPL','MSFT','AAPL','MSFT']


def test_version_selection_is_explicit(store,saved,canonical,dataset_options):
    store.save_dataset(canonical,dataset_id='second_snapshot',source_frames={'bars':canonical},**dataset_options)
    assert load_dataset(saved['dataset_id'],store=store).attrs['manifests'][0]['dataset_id']==saved['dataset_id']
    with pytest.raises(TypeError): load_dataset(store=store)


def test_checksum_checked_before_filter(store,saved,canonical):
    path=store.resolve(saved['normalized_files']['bars']['path'])
    canonical.loc[len(canonical)-1,'close']+=.5;canonical.to_parquet(path,index=False)
    with pytest.raises(ValueError,match='checksum'):
        load_dataset(saved['dataset_id'],start='2020-01-08T00:00Z',end='2020-01-15T00:00Z',store=store)


@pytest.mark.parametrize('basis',['adjusted','unknown'])
def test_unknown_price_basis(store,saved,basis):
    with pytest.raises(ValueError,match='Unknown price basis'):
        load_dataset(saved['dataset_id'],price_basis=basis,store=store)


def test_symbol_timeframe_and_range_validation(store,saved):
    for options in [{'symbols':['MSFT']},{'timeframe':'15m'},{'start':'2020-01-01'},
        {'start':'2020-01-10T00:00Z','end':'2020-01-01T00:00Z'}]:
        with pytest.raises(ValueError): load_dataset(saved['dataset_id'],store=store,**options)
