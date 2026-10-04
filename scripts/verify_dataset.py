"""Verify local manifest, all checksums, schema and canonical data; no network."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.loader import verify_dataset
from src.data.store import DataStore


def dataset_arguments(parser):
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--dataset-id')
    group.add_argument('--manifest', type=Path)
    group.add_argument('--legacy-path', type=Path)
    parser.add_argument('--data-config', type=Path, default=ROOT / 'config/data.yaml')
    parser.add_argument('--root', type=Path, default=ROOT)


def read_dataset(args):
    store = DataStore.from_config(args.data_config, args.root)
    return verify_dataset(dataset_id=args.dataset_id, manifest_path=args.manifest,
                          legacy_path=args.legacy_path, store=store)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    dataset_arguments(parser)
    args = parser.parse_args()
    try:
        manifest, frames = read_dataset(args)
        bars = frames['bars']
        print(f"PASS dataset_id={manifest['dataset_id']} provider={manifest['provider']} "
              f"market={manifest['market']} symbols={manifest['symbols']} rows={len(bars)} "
              f"range={bars.date.min().date()}..{bars.date.max().date()} "
              f"SHA={manifest['normalized_sha256']}")
    except Exception as error:
        print(f'FAIL {type(error).__name__}: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
