"""Observe verified bars with Chan primitives; export structures without trades."""
import argparse
import json
from pathlib import Path
from quant_lab.data.store import DataStore, ROOT
from quant_lab.data.loader import load_dataset, iter_bars
from quant_lab.data.inspection import write_chan_outputs
from quant_lab.chan import ChanConfig
from quant_lab.strategies.base import StrategyContext
from quant_lab.strategies.chan_fx import ChanFxStrategy


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-id',required=True)
    parser.add_argument('--symbol',required=True)
    parser.add_argument('--start')
    parser.add_argument('--end')
    parser.add_argument('--session-timezone',help='Explicit V2 session-label adapter timezone')
    parser.add_argument('--initial-direction-policy',choices=['error','up','down'],default='error')
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--plot',action='store_true')
    args=parser.parse_args()
    store=DataStore(args.root)
    data=load_dataset(args.dataset_id,store=store,symbols=[args.symbol],start=args.start,end=args.end,
        session_timezone=args.session_timezone)
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
