"""Local immutable files. A manifest publishes a dataset only after all files exist."""
from datetime import datetime, timezone
from pathlib import Path
import json
import pandas as pd
import yaml
from src.data.manifest import (file_sha256, safe_component, read_manifest,
                               write_manifest, validate_manifest)
from src.data.validation import (validate_adjustments,
                                 validate_corporate_actions, validate_instruments,
                                 validate_calendar)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORAGE = {'source_dir': 'data/source', 'normalized_dir': 'data/normalized',
                   'reference_dir': 'data/reference', 'manifest_dir': 'data/manifests'}
VALIDATORS = {'adjustments': validate_adjustments, 'corporate_actions': validate_corporate_actions,
              'instruments': validate_instruments, 'calendar': validate_calendar}


class DataStore:
    def __init__(self, root=ROOT, storage=None):
        self.root = Path(root).resolve()
        self.storage = dict(DEFAULT_STORAGE if storage is None else storage)
        if set(self.storage) != set(DEFAULT_STORAGE):
            raise ValueError('storage keys must specify source, normalized, reference, manifest directories')
        for value in self.storage.values():
            self.resolve(value)

    @classmethod
    def from_config(cls, path, root=ROOT):
        with Path(path).open() as handle:
            config = yaml.safe_load(handle)
        return cls(root, config['storage'])

    def resolve(self, relative):
        relative = Path(relative)
        path = (self.root / relative).resolve()
        if relative.is_absolute() or not path.is_relative_to(self.root):
            raise ValueError('Store paths must remain inside root')
        return path

    def manifest_path(self, dataset_id):
        return self.resolve(Path(self.storage['manifest_dir']) / (safe_component(dataset_id) + '.json'))

    def _save_frame(self, relative, frame, preserve_index=False):
        path = self.resolve(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as handle:
            frame.to_parquet(handle, index=preserve_index, engine='pyarrow')
        return {'path': str(relative), 'sha256': file_sha256(path)}

    def freeze_sources(self, dataset_id, provider, frames):
        directory = Path(self.storage['source_dir']) / safe_component(provider) / safe_component(dataset_id)
        if self.resolve(directory).exists():
            raise FileExistsError(f'Refusing to overwrite frozen source: {directory}')
        if 'identity' in frames:
            raise ValueError('identity is a reserved source name')
        if 'bars' not in frames or not isinstance(frames['bars'], pd.DataFrame) or frames['bars'].empty:
            raise ValueError('Provider returned no bars')
        entries = {}
        for name, frame in frames.items():
            safe_component(name)
            if isinstance(frame, pd.DataFrame):
                entries[name] = self._save_frame(directory / (name + '.parquet'), frame, preserve_index=True)
            elif isinstance(frame, bytes):
                relative = directory / (name + '.bin')
                path = self.resolve(relative)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('xb') as handle:
                    handle.write(frame)
                entries[name] = {'path': str(relative), 'sha256': file_sha256(path)}
            elif isinstance(frame, dict):
                relative = directory / (name + '.json')
                path = self.resolve(relative)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('x') as handle:
                    json.dump(frame, handle, indent=2, allow_nan=False)
                entries[name] = {'path': str(relative), 'sha256': file_sha256(path)}
            else:
                raise ValueError('Source must be a DataFrame or JSON object')
        return entries

    def load_manifest(self, dataset_id):
        return read_manifest(self.manifest_path(dataset_id))

    def read_frame(self, entry):
        path = self.resolve(entry['path'])
        if file_sha256(path) != entry['sha256']:
            raise ValueError(f'Dataset checksum mismatch: {path}')
        return pd.read_parquet(path)

    def save_dataset(self, bars, *, dataset_id, provider, provider_version, instruments,
                     timeframe, source_timezone, source_frames=None, source_files=None,
                     assumptions=(), session_timezone=None, aggregation_timezone=None,
                     anchor=None, lineage=None, normalized_frames=None):
        """Publish a dataset only after the frozen sources and normalized files verify."""
        from dataclasses import asdict
        from zoneinfo import ZoneInfo
        from src.market import Instrument, Timeframe
        from src.data.validation import validate_bars
        from src.data.manifest import IDENTITY_KEYS
        timeframe = Timeframe.parse(timeframe)
        validate_bars(bars, timeframe)
        safe_component(dataset_id)
        safe_component(provider)
        ZoneInfo(source_timezone)
        for zone in (session_timezone, aggregation_timezone):
            if zone is not None:
                ZoneInfo(zone)
        instruments = [x if isinstance(x, Instrument) else Instrument(**x) for x in instruments]
        symbols = sorted(bars.symbol.unique().tolist())
        if sorted(x.symbol for x in instruments) != symbols or len(set(symbols)) != len(instruments):
            raise ValueError('Instrument/symbol mismatch')
        if len({(x.asset_class, x.venue) for x in instruments}) != 1:
            raise ValueError('One asset class and venue per frozen dataset required')
        item = instruments[0]
        label = item.symbol if len(symbols) == 1 else 'multi'
        for value in (item.venue, label):
            safe_component(value)
        source_dir = Path(self.storage['source_dir']) / provider / dataset_id
        manifest_path = self.manifest_path(dataset_id)
        if manifest_path.exists() or manifest_path.with_suffix('.json.sha256').exists():
            raise FileExistsError('Refusing to overwrite frozen dataset')
        if source_frames is None and source_files is None:
            raise ValueError('Source snapshots are required')
        if source_files is None:
            source_files = self.freeze_sources(dataset_id, provider, source_frames)
        source_files = {name: dict(entry) for name, entry in source_files.items()}
        for entry in source_files.values():
            path = self.resolve(entry['path'])
            if not path.is_relative_to(self.resolve(source_dir)) or file_sha256(path) != entry['sha256']:
                raise ValueError('Source identity/path/checksum mismatch')
        if self.resolve(source_dir / 'identity.json').exists():
            raise FileExistsError('Refusing to overwrite frozen identity')
        frames = dict(normalized_frames or {})
        if 'bars' in frames:
            raise ValueError('bars is a reserved normalized name')
        frames = {'bars': bars, **frames}
        normalized = {}
        for name, frame in frames.items():
            safe_component(name)
            relative = (Path(self.storage['normalized_dir']) / name / item.asset_class.value /
                item.venue / timeframe.value / label / dataset_id / (name + '.parquet'))
            normalized[name] = self._save_frame(relative, frame)
        manifest = {'schema_version': 3, 'normalizer_version': 3, 'dataset_id': dataset_id,
            'provider': provider, 'provider_version': str(provider_version),
            'instruments': [{**asdict(x), 'asset_class': x.asset_class.value} for x in instruments],
            'symbols': symbols, 'timeframe': timeframe.value, 'timestamp_semantics': 'bar_start',
            'source_timezone': source_timezone, 'session_timezone': session_timezone,
            'aggregation_timezone': aggregation_timezone, 'anchor': anchor, 'lineage': lineage,
            'actual_start': bars.timestamp.min().isoformat(), 'actual_end': bars.timestamp.max().isoformat(),
            'rows': len(bars), 'downloaded_at_utc': datetime.now(timezone.utc).isoformat(),
            'price_data': {'raw_ohlc': True, 'adjustment_available': 'adjustments' in frames,
                'provider_adjusted_available': bool('adjustments' in frames and
                    frames['adjustments'].factor_semantics.eq('provider_adjusted_close_ratio').all())},
            'assumptions': list(assumptions), 'source_files': source_files,
            'normalized_files': normalized, 'source_sha256': source_files['bars']['sha256'],
            'normalized_sha256': normalized['bars']['sha256']}
        identity_path = source_dir / 'identity.json'
        path = self.resolve(identity_path)
        with path.open('x') as handle:
            json.dump({key: manifest[key] for key in IDENTITY_KEYS}, handle, allow_nan=False)
        manifest['source_files']['identity'] = {'path': str(identity_path), 'sha256': file_sha256(path)}
        self.verify(manifest)
        write_manifest(manifest_path, manifest)
        return manifest

    def verify(self, manifest):
        validate_manifest(manifest)
        from src.data.validation import validate_bars
        from src.data.manifest import IDENTITY_KEYS
        for entry in manifest['source_files'].values():
            if file_sha256(self.resolve(entry['path'])) != entry['sha256']:
                raise ValueError('Source checksum mismatch')
        identity = manifest['source_files'].get('identity')
        if identity is None:
            raise ValueError('Missing frozen request identity')
        request = json.loads(self.resolve(identity['path']).read_text())
        if set(request) != set(IDENTITY_KEYS) or any(request[key] != manifest[key] for key in IDENTITY_KEYS):
            raise ValueError('Manifest request identity mismatch')
        frames = {name: self.read_frame(entry) for name, entry in manifest['normalized_files'].items()}
        bars = frames['bars']
        validate_bars(bars, manifest['timeframe'])
        if (len(bars) != manifest['rows'] or sorted(bars.symbol.unique().tolist()) != manifest['symbols']
                or bars.timestamp.min().isoformat() != manifest['actual_start']
                or bars.timestamp.max().isoformat() != manifest['actual_end']):
            raise ValueError('Manifest symbol/rows/timestamp range mismatch')
        for name, frame in frames.items():
            if name != 'bars':
                if name not in VALIDATORS:
                    raise ValueError(f'Unknown normalized frame: {name}')
                VALIDATORS[name](frame)
                if 'provider' in frame and not frame.provider.eq(manifest['provider']).all():
                    raise ValueError('Manifest provider mismatch')
                if 'symbol' in frame and not frame.symbol.isin(manifest['symbols']).all():
                    raise ValueError('Manifest reference symbol mismatch')
        if 'instruments' in frames and sorted(frames['instruments'].symbol) != manifest['symbols']:
            raise ValueError('Manifest instrument symbol mismatch')
        if 'adjustments' in frames:
            if 'date' not in bars:
                raise ValueError('Equity adjustments require explicit session keys')
            factors = frames['adjustments']
            matched = bars[['date','symbol']].merge(factors,on=['date','symbol'],how='left',validate='one_to_one')
            if matched.adj_factor.isna().any():
                raise ValueError('Adjustments must cover every frozen bar key')
            available = bool(factors.factor_semantics.eq('provider_adjusted_close_ratio').all())
            if manifest['price_data']['provider_adjusted_available'] != available:
                raise ValueError('Manifest adjustment semantics mismatch')
        if manifest['price_data']['adjustment_available'] != ('adjustments' in frames):
            raise ValueError('Adjustment availability mismatch')
        return frames
