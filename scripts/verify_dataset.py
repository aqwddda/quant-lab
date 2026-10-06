"""Verify local manifest, all checksums, schema and canonical data; no network."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

from quant_lab.data.loader import verify_dataset
from quant_lab.data.store import DataStore


from quant_lab.data.inspection import dataset_arguments, read_dataset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    dataset_arguments(parser)
    args = parser.parse_args()
    try:
        manifest, frames = read_dataset(args)
        bars = frames['bars']
        dates = bars['timestamp' if manifest['schema_version'] == 3 else 'date']
        print(f"PASS dataset_id={manifest['dataset_id']} provider={manifest['provider']} "
              f"market={manifest.get('market', [x['venue'] for x in manifest.get('instruments', [])])} symbols={manifest['symbols']} rows={len(bars)} "
              f"range={dates.min()}..{dates.max()} "
              f"SHA={manifest['normalized_sha256']}")
    except Exception as error:
        print(f'FAIL {type(error).__name__}: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
