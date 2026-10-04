"""Explicit provider download -> source snapshot -> canonical frozen dataset."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml
from src.data.store import DataStore
from src.data.manifest import safe_component
from src.data.normalize import normalize_yahoo, normalize_tushare
from src.data.providers import get_provider, PROVIDERS
from src.data.providers.base import check_request


def download_data(output: Path, start: str, end: str):
    """V1 API compatibility; the CLI below always uses the V2 pipeline."""
    metadata = get_provider('yahoo', cache_dir=ROOT / '.cache/yfinance').download_legacy(output, start, end)
    print(json.dumps(metadata, indent=2))
    return metadata


def download_dataset(provider, market, symbol, start, end, frequency='1d', *, store=None,
                     dataset_id=None, provider_instance=None, provider_options=None):
    check_request(symbol, start, end, frequency)
    if provider not in PROVIDERS:
        raise ValueError(f'Unknown provider: {provider}')
    if market != PROVIDERS[provider].market:
        raise ValueError(f'{provider} does not support market {market}')
    store = store or DataStore()
    timestamp = datetime.now(timezone.utc)
    dataset_id = dataset_id or f"{provider}_{market}_{symbol}_{frequency}_{start.replace('-', '')}_{end.replace('-', '')}_{timestamp:%Y%m%dT%H%M%S%fZ}"
    safe_component(dataset_id)
    source_dir = Path(store.storage['source_dir']) / provider / dataset_id
    if store.manifest_path(dataset_id).exists() or store.resolve(source_dir).exists():
        raise FileExistsError(f'Refusing to overwrite frozen dataset: {dataset_id}')
    transport = provider_instance or get_provider(provider, **(provider_options or {}))
    if transport.name != provider or transport.market != market:
        raise ValueError('Provider identity/market mismatch')
    snapshot = transport.fetch_snapshot(symbol, start, end, frequency)
    # Preserve the actual response first, including invalid responses for audit.
    sources = store.freeze_sources(dataset_id, provider, snapshot.source_frames)
    normalize = {'yahoo': normalize_yahoo, 'tushare': normalize_tushare}[provider]
    normalized = normalize(snapshot.prepared, symbol)
    return store.save_dataset(**normalized, dataset_id=dataset_id, provider=provider,
        provider_version=snapshot.provider_version, market=market,
        asset_type=normalized['instruments'].asset_type.iloc[0], start=start, end=end,
        source_files=sources, assumptions=snapshot.assumptions,
        downloaded_at_utc=datetime.now(timezone.utc).isoformat())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', default='yahoo')
    parser.add_argument('--market', default='US')
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
    options = {'cache_dir': args.root / '.cache/yfinance'} if args.provider == 'yahoo' else {'token_env': settings['token_env']}
    manifest = download_dataset(args.provider, args.market, args.symbol, args.start, args.end,
        args.frequency or config['defaults']['frequency'], store=DataStore(args.root, config['storage']),
        dataset_id=args.dataset_id, provider_options=options)
    print(json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
