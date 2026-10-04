import pandas as pd
import pytest
from src.data.loader import load_bars


def test_single_symbol_range(store, saved, canonical):
    loaded = load_bars('US', ['AAPL'], '2020-01-08', '2020-01-15', store=store)
    pd.testing.assert_frame_equal(loaded, canonical.loc[canonical.date.between('2020-01-08', '2020-01-15')].reset_index(drop=True))
    assert loaded.attrs['manifests'][0]['dataset_id'] == saved['dataset_id']


def test_multi_symbol_long_format(store, saved, canonical):
    other = canonical.copy()
    other['symbol'] = 'MSFT'
    store.save_dataset(other, dataset_id='fixture_US_MSFT_v1', provider='fixture',
                       provider_version='1', market='US', asset_type='EQUITY',
                       start='2020-01-01', end=str(other.date.iloc[-1].date()),
                       source_frames={'bars': other})
    data = load_bars('US', ['MSFT', 'AAPL'], '2020-01-01', str(other.date.iloc[-1].date()), store=store)
    assert len(data) == len(canonical) * 2
    assert not data.duplicated(['date', 'symbol']).any()
    assert data.symbol.iloc[:4].tolist() == ['AAPL', 'MSFT', 'AAPL', 'MSFT']
    assert data[['date', 'symbol']].equals(data.sort_values(['date', 'symbol'])[['date', 'symbol']])


def test_ambiguous_version_needs_explicit_selection(store, saved, canonical):
    store.save_dataset(canonical, dataset_id='fixture_US_AAPL_v2', provider='fixture',
                       provider_version='1', market='US', asset_type='EQUITY', start='2020-01-01',
                       end=str(canonical.date.iloc[-1].date()), source_frames={'bars': canonical})
    with pytest.raises(ValueError, match='Multiple frozen versions'):
        load_bars('US', ['AAPL'], '2020-01-01', '2020-01-10', store=store)
    assert len(load_bars('US', ['AAPL'], '2020-01-01', '2020-01-10', store=store,
                         dataset_id=saved['dataset_id'])) == 8


def test_checksum_checked_before_date_filter(store, saved, canonical):
    path = store.resolve(saved['normalized_files']['bars']['path'])
    canonical.loc[len(canonical) - 1, 'close'] += 0.5
    canonical.to_parquet(path, index=False)
    with pytest.raises(ValueError, match='checksum'):
        load_bars('US', ['AAPL'], '2020-01-01', '2020-01-10', store=store)


@pytest.mark.parametrize('basis', ['adjusted', 'unknown'])
def test_unknown_basis(store, basis):
    with pytest.raises(ValueError, match='Unknown price basis'):
        load_bars('US', ['AAPL'], '2020-01-01', '2020-01-10', price_basis=basis, store=store)


def test_explicit_per_symbol_versions(store, saved, canonical):
    for symbol, version in [('AAPL', 'v2'), ('MSFT', 'v1'), ('MSFT', 'v2')]:
        frame = canonical.copy()
        frame['symbol'] = symbol
        store.save_dataset(frame, dataset_id=f'{symbol}_{version}', provider='fixture', provider_version='1',
                           market='US', asset_type='EQUITY', start='2020-01-01',
                           end=str(frame.date.iloc[-1].date()), source_frames={'bars': frame})
    data = load_bars('US', ['AAPL', 'MSFT'], '2020-01-01', '2020-01-10', store=store,
                     dataset_id={'AAPL': saved['dataset_id'], 'MSFT': 'MSFT_v2'})
    assert len(data) == 16
    assert {m['dataset_id'] for m in data.attrs['manifests']} == {saved['dataset_id'], 'MSFT_v2'}
