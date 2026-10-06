"""Inspect verified frozen datasets and their explicit price basis; no network."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

from quant_lab.data.inspection import dataset_arguments, read_dataset
from quant_lab.data.adjustment import adjust_bars
from quant_lab.data.schema import PRICE_BASES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    dataset_arguments(parser)
    parser.add_argument('--price-basis', choices=sorted(PRICE_BASES), default=None)
    args = parser.parse_args()
    manifest, frames = read_dataset(args)
    basis = args.price_basis or manifest.get('price_basis', 'raw')
    bars = frames['bars']
    if manifest['schema_version'] == 1:
        if basis != 'legacy_provider_adjusted':
            raise ValueError('Legacy adjusted data cannot be relabeled as raw or another basis')
    elif basis != 'raw':
        bars = adjust_bars(bars, frames.get('adjustments'), method=basis,
                           anchor_end=manifest['requested_end_inclusive'])
    key = 'timestamp' if manifest['schema_version'] == 3 else 'date'
    dates = bars[key]
    print(json.dumps({'dataset_id': manifest['dataset_id'], 'provider': manifest['provider'],
        'market': manifest.get('market', [x['venue'] for x in manifest.get('instruments', [])]), 'symbols': manifest['symbols'], 'price_basis': basis,
        'actual_start': str(dates.min()), 'actual_end': str(dates.max()),
        'rows': len(bars), 'missing_values': bars.isna().sum().to_dict(),
        'duplicate_keys': int(bars.duplicated([key, 'symbol']).sum()),
        'SHA': manifest['normalized_sha256'], 'manifest': manifest}, indent=2, allow_nan=False))
    print('First rows:\n' + bars.head().to_string(index=False))
    print('Last rows:\n' + bars.tail().to_string(index=False))


if __name__ == '__main__':
    main()
