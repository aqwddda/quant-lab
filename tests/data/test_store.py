import pandas as pd
import pytest


def test_round_trip_and_frozen_version(store,saved,canonical,dataset_options):
    manifest=store.load_manifest(saved['dataset_id'])
    from src.market import Instrument
    assert [Instrument(**item) for item in manifest['instruments']] == dataset_options['instruments']
    assert 'instruments' not in manifest['normalized_files']
    pd.testing.assert_frame_equal(store.verify(manifest)['bars'],canonical)
    with pytest.raises(FileExistsError):
        store.save_dataset(canonical,dataset_id=saved['dataset_id'],source_frames={'bars':canonical},**dataset_options)
    pd.testing.assert_frame_equal(store.verify(manifest)['bars'],canonical)


def test_missing_dataset_never_downloads(store):
    with pytest.raises(FileNotFoundError): store.load_manifest('missing')


def test_path_escape(store):
    with pytest.raises(ValueError): store.resolve('../secret')


def test_sources_required_before_writing(store,canonical,dataset_options):
    with pytest.raises(ValueError,match='Source snapshots'):
        store.save_dataset(canonical,dataset_id='invalid',**dataset_options)
    assert not store.resolve('data/normalized').exists()


def test_second_instrument_table_is_rejected_before_writing(store, canonical, dataset_options):
    with pytest.raises(ValueError, match='Unknown normalized frames'):
        store.save_dataset(canonical, dataset_id='invalid', source_frames={'bars': canonical},
            normalized_frames={'instruments': pd.DataFrame({'symbol': ['AAPL']})}, **dataset_options)
    assert not store.resolve('data/source').exists()
    assert not store.resolve('data/normalized').exists()
