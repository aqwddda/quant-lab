"""Explicit provider download -> source snapshot -> canonical frozen dataset."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

import yaml
from src.data.store import DataStore
from src.data.manifest import safe_component
from src.data.normalization.yahoo import normalize_yahoo
from src.data.normalization.tushare import normalize_tushare
from src.data.providers import get_provider, PROVIDERS
from src.data.providers.base import check_request


def download_dataset(provider, symbol, start, end, timeframe='1d', *, store=None,
                        dataset_id=None, provider_instance=None, provider_options=None):
    """Freeze supplier snapshots and publish the current canonical schema."""
    from src.market import AssetClass, Timeframe
    from src.data.normalization import instruments_from_reference
    store = store or DataStore()
    timeframe = Timeframe.parse(timeframe)
    transport = provider_instance or get_provider(provider, **(provider_options or {}))
    transport.capabilities.require(AssetClass.EQUITY, timeframe)
    if transport.name != provider:
        raise ValueError('Provider identity mismatch')
    stamp = datetime.now(timezone.utc)
    dataset_id = dataset_id or f'{provider}_{symbol}_{timeframe.value}_{stamp:%Y%m%dT%H%M%S%fZ}'
    safe_component(dataset_id)
    directory = Path(store.storage['source_dir']) / provider / dataset_id
    if store.manifest_path(dataset_id).exists() or store.resolve(directory).exists():
        raise FileExistsError('Refusing to overwrite frozen dataset')
    snapshot = transport.fetch_snapshot(symbol, start, end, timeframe.value)
    sources = store.freeze_sources(dataset_id, provider, {**snapshot.source_frames,
        'request': {'symbol':symbol,'start':start,'end_inclusive':end,'timeframe':timeframe.value}})
    normalized = {'yahoo': normalize_yahoo, 'tushare': normalize_tushare}[provider](snapshot.prepared, symbol)
    zone = transport.exchange_timezone if provider == 'yahoo' else 'Asia/Shanghai'
    bars = normalized['bars']
    instruments = instruments_from_reference(normalized['instruments'])
    return store.save_dataset(bars, dataset_id=dataset_id, provider=provider,
        provider_version=snapshot.provider_version, instruments=instruments, timeframe=timeframe,
        source_timezone=zone, session_timezone=zone, source_files=sources,
        normalized_frames={key:value for key,value in normalized.items() if key != 'bars'},
        assumptions=[*snapshot.assumptions,
            'Daily timestamp is exchange-session midnight converted to UTC; it is not an intraday exchange opening timestamp.'])


def import_local_dataset(path, *, instrument, timeframe, source_timezone, timestamp_semantics,
                         store=None, dataset_id=None):
    from src.data.providers.local import LocalBarProvider
    from src.data.normalization.local import normalize_local
    store = store or DataStore()
    stamp = datetime.now(timezone.utc)
    dataset_id = dataset_id or f'local_{instrument.symbol}_{stamp:%Y%m%dT%H%M%S%fZ}'
    safe_component(dataset_id)
    if store.manifest_path(dataset_id).exists() or store.resolve(Path(store.storage['source_dir']) / 'local' / dataset_id).exists():
        raise FileExistsError('Refusing to overwrite frozen dataset')
    snapshot = LocalBarProvider().fetch_snapshot(path, instrument=instrument, timeframe=timeframe,
        source_timezone=source_timezone, timestamp_semantics=timestamp_semantics)
    sources = store.freeze_sources(dataset_id, 'local', snapshot.source_frames)
    bars = normalize_local(snapshot.prepared)
    return store.save_dataset(bars, dataset_id=dataset_id, provider='local', provider_version=snapshot.provider_version,
        instruments=[instrument], timeframe=timeframe, source_timezone=source_timezone,
        source_files=sources, assumptions=[*snapshot.assumptions,
            f'Source timestamp semantics: {timestamp_semantics}; canonical timestamp semantics: bar_start.',
            'Fixed elapsed-time bar duration; no inferred broker sessions or daily rollover.'])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', default='yahoo')
    parser.add_argument('--market', default='US')
    parser.add_argument('--input', type=Path)
    parser.add_argument('--asset-class', choices=['equity','forex','futures'])
    parser.add_argument('--venue')
    parser.add_argument('--provider-symbol')
    parser.add_argument('--source-timezone')
    parser.add_argument('--timestamp-semantics', choices=['bar_start','bar_end'])
    parser.add_argument('--symbol', default='SPY')
    parser.add_argument('--start', default='2015-01-01')
    parser.add_argument('--end', default='2025-12-31')
    parser.add_argument('--frequency', default=None)
    parser.add_argument('--dataset-id', help='Optional explicit version name; refuses existing versions')
    parser.add_argument('--data-config', type=Path, default=ROOT / 'config/data.yaml')
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    with args.data_config.open() as handle:
        config = yaml.safe_load(handle)
    if args.provider not in config['providers']:
        raise ValueError(f'Unknown provider: {args.provider}')
    settings = config['providers'][args.provider]
    if settings.get('enabled') is not True:
        raise ValueError(f'Provider disabled: {args.provider}')
    if args.provider == 'local':
        if any(value is None for value in [args.input,args.asset_class,args.venue,args.provider_symbol,args.source_timezone,args.timestamp_semantics,args.frequency]):
            raise ValueError('Local import requires input, asset-class, venue, provider-symbol, source-timezone, timestamp-semantics and frequency')
        from src.market import Instrument
        manifest = import_local_dataset(args.input, instrument=Instrument(args.symbol,args.provider_symbol,args.asset_class,args.venue),
            timeframe=args.frequency, source_timezone=args.source_timezone, timestamp_semantics=args.timestamp_semantics,
            store=DataStore(args.root,config['storage']),dataset_id=args.dataset_id)
        print(json.dumps(manifest,indent=2,ensure_ascii=False,allow_nan=False))
        return
    options = {'cache_dir': args.root / '.cache/yfinance'} if args.provider == 'yahoo' else {'token_env': settings['token_env']}
    if args.provider not in PROVIDERS or args.market != PROVIDERS[args.provider].market:
        raise ValueError('Provider/market mismatch')
    manifest = download_dataset(args.provider, args.symbol, args.start, args.end,
        args.frequency or config['defaults']['frequency'], store=DataStore(args.root, config['storage']),
        dataset_id=args.dataset_id, provider_options=options)
    print(json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
