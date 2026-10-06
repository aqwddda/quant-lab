"""Arguments shared by local dataset inspection commands."""
from pathlib import Path
from quant_lab.data.store import ROOT, DataStore
from quant_lab.data.loader import verify_dataset

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


