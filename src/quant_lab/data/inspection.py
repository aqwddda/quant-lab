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




def write_chan_outputs(analyzer, output, *, audit=None, plot=False):
    """Flatten immutable as-known snapshots for manual inspection outside Chan."""
    import json
    from dataclasses import asdict
    import pandas as pd
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    raw = [{**asdict(b), 'timeframe': b.timeframe.value} for b in analyzer.raw_bars]
    merged = [{'index': b.index, 'high': b.high, 'low': b.low,
        'start_timestamp': b.start_timestamp, 'end_timestamp': b.end_timestamp,
        'available_at': b.available_at, 'raw_indices': list(b.raw_indices),
        'direction': b.direction.value if b.direction else None} for b in analyzer.merged_bars]
    fractals = [{'type': f.type.value, 'left_index': f.left.index, 'center_index': f.center.index,
        'right_index': f.right.index, 'pivot_time': f.pivot_time, 'confirmed_at': f.confirmed_at,
        'price': f.price, 'left_raw_indices': list(f.left.raw_indices),
        'center_raw_indices': list(f.center.raw_indices), 'right_raw_indices': list(f.right.raw_indices),
        'left_high': f.left.high, 'left_low': f.left.low, 'center_high': f.center.high,
        'center_low': f.center.low, 'right_high': f.right.high, 'right_low': f.right.low}
        for f in analyzer.fractals]
    strokes = [{'start_index': s.start.center.index, 'end_index': s.end.center.index,
        'start_pivot_time': s.start.pivot_time, 'end_pivot_time': s.end.pivot_time,
        'start_price': s.start.price, 'end_price': s.end.price, 'direction': s.direction.value,
        'status': s.status.value, 'formed_at': s.end.confirmed_at, 'confirmed_at': s.confirmed_at}
        for s in analyzer.strokes]
    columns = {'raw_bars': ['timestamp','symbol','open','high','low','close','timeframe','volume','tick_volume','amount','open_interest'],
        'merged_bars': ['index','high','low','start_timestamp','end_timestamp','available_at','raw_indices','direction'],
        'fractals': ['type','left_index','center_index','right_index','pivot_time','confirmed_at','price',
            'left_raw_indices','center_raw_indices','right_raw_indices','left_high','left_low','center_high','center_low','right_high','right_low'],
        'strokes': ['start_index','end_index','start_pivot_time','end_pivot_time','start_price','end_price','direction','status','formed_at','confirmed_at']}
    tables = {'raw_bars': raw, 'merged_bars': merged, 'fractals': fractals, 'strokes': strokes}
    for name, rows in tables.items():
        pd.DataFrame(rows, columns=columns[name]).to_csv(output / (name + '.csv'), index=False)
    def encode(value):
        if hasattr(value,'isoformat'):
            return value.isoformat()
        raise TypeError(f'Unsupported JSON value: {type(value)}')
    (output / 'chan.json').write_text(json.dumps({'audit': audit or {}, **tables},default=encode,
        indent=2,ensure_ascii=False,allow_nan=False))
    if plot:
        import os
        os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,ax=plt.subplots(figsize=(12,5),layout='constrained')
        ax.plot([b.timestamp for b in analyzer.raw_bars],[b.close for b in analyzer.raw_bars],label='raw close',alpha=.45)
        for stroke in analyzer.strokes:
            ax.plot([stroke.start.pivot_time,stroke.end.pivot_time],[stroke.start.price,stroke.end.price],
                color='tab:blue',linestyle='-' if stroke.confirmed_at else '--')
        ax.set(xlabel='UTC bar start / merged pivot',ylabel='Price',title='Chan structure; dashed final stroke is tentative')
        ax.grid(alpha=.2)
        ax.legend()
        fig.savefig(output/'chan.png',dpi=150)
        plt.close(fig)
    return {name:len(rows) for name,rows in tables.items()}
