from copy import deepcopy
import pytest
from src.data.manifest import read_manifest, validate_manifest


def test_manifest_self_checksum(store, saved):
    path = store.manifest_path(saved['dataset_id'])
    path.write_text(path.read_text() + ' ')
    with pytest.raises(ValueError, match='Manifest checksum'):
        read_manifest(path)


@pytest.mark.parametrize('field,value', [('symbols', ['MSFT']), ('provider', 'other'),
                                        ('actual_end', '2020-06-15'), ('rows', 119)])
def test_identity_and_data_metadata(store, saved, field, value):
    manifest = deepcopy(saved)
    manifest[field] = value
    with pytest.raises(ValueError):
        store.verify(manifest)


def test_checksum_mismatch(store, saved):
    path = store.resolve(saved['normalized_files']['bars']['path'])
    with path.open('ab') as handle:
        handle.write(b'corruption')
    with pytest.raises(ValueError, match='checksum'):
        store.verify(saved)


def test_missing_file(store, saved):
    store.resolve(saved['normalized_files']['bars']['path']).unlink()
    with pytest.raises(FileNotFoundError):
        store.verify(saved)


def test_wrong_date_range(saved):
    saved['actual_start'] = '2019-12-31'
    with pytest.raises(ValueError, match='date range'):
        validate_manifest(saved)
