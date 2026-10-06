"""Observe verified bars with Chan primitives; export structures without trades."""
import argparse
import sys
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from src.data.store import DataStore, ROOT
from src.data.loader import load_dataset, iter_bars
from src.data.inspection import write_chan_outputs
from src.chan import ChanAnalyzer, ChanConfig


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    identity = parser.add_mutually_exclusive_group(required=True)
    identity.add_argument('--dataset-id')
    identity.add_argument('--manifest',type=Path)
    parser.add_argument('--symbol',required=True)
    parser.add_argument('--start')
    parser.add_argument('--end')
    parser.add_argument('--initial-direction-policy',choices=['error','up','down'],default='error')
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--plot',action='store_true')
    args=parser.parse_args()
    store=DataStore(args.root)
    data=load_dataset(args.dataset_id,manifest_path=args.manifest,store=store,
        symbols=[args.symbol],start=args.start,end=args.end)
    manifest=data.attrs['manifests'][0]
    analyzer=ChanAnalyzer(ChanConfig(args.initial_direction_policy))
    for bar in iter_bars(data):
        analyzer.update(bar)
    output=args.output or ROOT/'reports'/('chan_'+manifest['dataset_id'])
    counts=write_chan_outputs(analyzer,output,plot=args.plot,audit={
        'mode':'structure_observation_only','dataset_id':manifest['dataset_id'],'symbol':args.symbol,
        'manifest':data.attrs['manifests'][0],'requested_start':args.start,'requested_end':args.end,
        'initial_direction_policy':args.initial_direction_policy,
        'assumptions':['Cold start at selected range; no preceding bars are analyzed.',
            'No orders, accounting, performance or undefined Chan trading rules.']})
    print(json.dumps({'output':str(output),**counts},ensure_ascii=False))


if __name__=='__main__':
    main()
