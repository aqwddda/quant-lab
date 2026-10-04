import pandas as pd
import pytest


def test_round_trip_and_frozen_version(store, saved, canonical):
    manifest = store.load_manifest(saved['dataset_id'])
    pd.testing.assert_frame_equal(store.verify(manifest)['bars'], canonical)
    with pytest.raises(FileExistsError):
        store.save_dataset(canonical, dataset_id=saved['dataset_id'], provider='fixture',
                           provider_version='1', market='US', asset_type='EQUITY',
                           start='2020-01-01', end=str(canonical.date.iloc[-1].date()),
                           source_frames={'bars': canonical})
    pd.testing.assert_frame_equal(store.verify(manifest)['bars'], canonical)


def test_no_network_fallback(store):
    with pytest.raises(FileNotFoundError, match='separately'):
        store.locate('US', ['AAPL'], '2020-01-01', '2020-12-31')


def test_path_escape(store):
    with pytest.raises(ValueError):
        store.resolve('../secret')


def test_request_and_sources_checked_before_writing(store, canonical):
    options = dict(dataset_id='invalid', provider='fixture', provider_version='1', market='US', asset_type='EQUITY')
    with pytest.raises(ValueError, match='outside requested'):
        store.save_dataset(canonical, **options, start='2020-01-01', end='2020-01-02', source_frames={'bars': canonical})
    with pytest.raises(ValueError, match='Source snapshots'):
        store.save_dataset(canonical, **options, start='2020-01-01', end=str(canonical.date.iloc[-1].date()))
    assert not store.resolve('data/normalized').exists()
