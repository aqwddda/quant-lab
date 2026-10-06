"""Freeze one explicitly anchored derived dataset from a verified canonical source."""
import argparse
import sys
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from src.data.store import DataStore, ROOT
from src.data.resample import resample_dataset


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dataset-id',required=True)
    parser.add_argument('--dataset-id',required=True)
    parser.add_argument('--target-timeframe',required=True)
    parser.add_argument('--aggregation-timezone',required=True)
    parser.add_argument('--anchor',required=True)
    parser.add_argument('--root',type=Path,default=ROOT)
    args=parser.parse_args()
    manifest=resample_dataset(args.source_dataset_id,dataset_id=args.dataset_id,
        target_timeframe=args.target_timeframe,aggregation_timezone=args.aggregation_timezone,
        anchor=args.anchor,store=DataStore(args.root))
    print(json.dumps(manifest,indent=2,ensure_ascii=False,allow_nan=False))


if __name__=='__main__':
    main()
