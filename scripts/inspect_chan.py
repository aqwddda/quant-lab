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
from src.chan import ChanConfig
from src.strategies.base import StrategyContext
from src.strategies.chan_fx import ChanFxStrategy


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-id',required=True)
    parser.add_argument('--symbol',required=True)
    parser.add_argument('--start')
    parser.add_argument('--end')
    parser.add_argument('--initial-direction-policy',choices=['error','up','down'],default='error')
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--plot',action='store_true')
    args=parser.parse_args()
    store=DataStore(args.root)
    data=load_dataset(args.dataset_id,store=store,symbols=[args.symbol],start=args.start,end=args.end)
    strategy=ChanFxStrategy(ChanConfig(args.initial_direction_policy))
    for i,bar in enumerate(iter_bars(data)):
        strategy.on_bar(StrategyContext(i,bar.available_at),bar)
    output=args.output or ROOT/'reports'/('chan_'+args.dataset_id)
    counts=write_chan_outputs(strategy.analyzer,output,plot=args.plot,audit={
        'mode':'structure_observation_only','dataset_id':args.dataset_id,'symbol':args.symbol,
        'manifest':data.attrs['manifests'][0],'requested_start':args.start,'requested_end':args.end,
        'initial_direction_policy':args.initial_direction_policy,
        'assumptions':['Cold start at selected range; no preceding bars are analyzed.',
            'No orders, accounting, performance or undefined Chan trading rules.']})
    print(json.dumps({'output':str(output),**counts},ensure_ascii=False))


if __name__=='__main__':
    main()
