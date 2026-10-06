"""Arguments shared by local dataset inspection commands."""
from pathlib import Path
from src.data.store import ROOT, DataStore
from src.data.loader import verify_dataset

def dataset_arguments(parser):
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--dataset-id')
    group.add_argument('--manifest', type=Path)
    parser.add_argument('--data-config', type=Path, default=ROOT / 'config/data.yaml')
    parser.add_argument('--root', type=Path, default=ROOT)


def read_dataset(args):
    store = DataStore.from_config(args.data_config, args.root)
    return verify_dataset(dataset_id=args.dataset_id, manifest_path=args.manifest,
                          store=store)




def write_chan_outputs(analyzer, output, *, audit=None, export_csv=True, export_json=True, plot=False):
    """Flatten immutable as-known snapshots for manual inspection outside Chan."""
    import json
    from dataclasses import asdict
    import pandas as pd
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    raw = [{**asdict(b), 'timeframe': b.timeframe.value, 'available_at': b.available_at}
        for b in analyzer.raw_bars]
    merged = [{'index': b.index, 'high': b.high, 'low': b.low,
        'start_timestamp': b.start_timestamp, 'end_timestamp': b.end_timestamp,
        'available_at': b.available_at, 'raw_indices': list(b.raw_indices),
        'direction': b.direction.value if b.direction else None,
        'raw_count': len(b.raw_indices)} for b in analyzer.merged_bars]
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
    columns = {'raw_bars': ['timestamp','symbol','open','high','low','close','timeframe','volume','tick_volume','amount','open_interest','available_at'],
        'merged_bars': ['index','high','low','start_timestamp','end_timestamp','available_at','raw_indices','direction','raw_count'],
        'fractals': ['type','left_index','center_index','right_index','pivot_time','confirmed_at','price',
            'left_raw_indices','center_raw_indices','right_raw_indices','left_high','left_low','center_high','center_low','right_high','right_low'],
        'strokes': ['start_index','end_index','start_pivot_time','end_pivot_time','start_price','end_price','direction','status','formed_at','confirmed_at']}
    tables = {'raw_bars': raw, 'merged_bars': merged, 'fractals': fractals, 'strokes': strokes}
    if export_csv:
        for name, rows in tables.items():
            pd.DataFrame(rows, columns=columns[name]).to_csv(output / (name + '.csv'), index=False)
    def encode(value):
        if hasattr(value,'isoformat'):
            return value.isoformat()
        raise TypeError(f'Unsupported JSON value: {type(value)}')
    if export_json:
        (output / 'chan.json').write_text(json.dumps({'audit': audit or {}, **tables},default=encode,
            indent=2,ensure_ascii=False,allow_nan=False), encoding='utf-8')
    counts = {name:len(rows) for name,rows in tables.items()}
    first = analyzer.raw_bars[0] if analyzer.raw_bars else None
    symbol = first.symbol if first else (audit or {}).get('symbol', 'unknown')
    timeframe = first.timeframe.value if first else (audit or {}).get('manifest', {}).get('timeframe', 'unknown')
    (output / '05_summary.txt').write_text('\n'.join([
        f'symbol: {symbol}', f'timeframe: {timeframe}',
        *[f'{name} count: {count}' for name, count in counts.items()],
        f'confirmed stroke count: {len(analyzer.confirmed_strokes)}',
        f'tentative stroke exists: {analyzer.current_stroke is not None}',
    ]) + '\n', encoding='utf-8')
    if plot:
        from src.visualization import (plot_raw_candles, plot_merged_bars,
            plot_chan_structure, plot_raw_with_chan_overlay)
        title = f'{symbol} | {timeframe}'
        if first:
            title += f' | {first.timestamp.isoformat()} -> {analyzer.raw_bars[-1].timestamp.isoformat()}'
        if (audit or {}).get('dataset_id'):
            title += f"\n{audit['dataset_id']}"
        structure_title = (f'{title}\n{len(analyzer.fractals)} fractals | {len(analyzer.strokes)} strokes | '
            f'{len(analyzer.confirmed_strokes)} confirmed')
        plot_raw_candles(analyzer.raw_bars, output / '01_raw_candles.png', title=title)
        plot_merged_bars(analyzer.merged_bars, output / '02_merged_bars.png', title=title)
        plot_chan_structure(analyzer.merged_bars, analyzer.fractals, analyzer.strokes,
            output / '03_chan_structure.png', title=structure_title)
        plot_raw_with_chan_overlay(analyzer.raw_bars, analyzer.fractals, analyzer.strokes,
            output / '04_raw_with_chan_overlay.png', title=structure_title)
    return counts
