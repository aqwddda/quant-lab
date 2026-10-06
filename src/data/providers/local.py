"""Read one supplied file; the frozen bytes are the provider response."""
from io import BytesIO
from pathlib import Path
import pandas as pd
from src.market import AssetClass, Timeframe, Instrument, TimestampSemantics
from src.data.models import ProviderSnapshot
from src.data.providers.base import ProviderCapabilities


class LocalBarProvider:
    name = 'local'
    version = '1'
    capabilities = ProviderCapabilities(frozenset(AssetClass), frozenset(Timeframe))

    def fetch_snapshot(self, path, *, instrument, timeframe, source_timezone, timestamp_semantics):
        from zoneinfo import ZoneInfo
        if not isinstance(instrument, Instrument):
            raise ValueError('Explicit Instrument required')
        timeframe = Timeframe.parse(timeframe)
        semantics = TimestampSemantics(timestamp_semantics)
        self.capabilities.require(instrument.asset_class, timeframe)
        ZoneInfo(source_timezone)
        path = Path(path)
        original = path.read_bytes()
        if path.suffix.lower() == '.csv':
            frame = pd.read_csv(BytesIO(original))
        elif path.suffix.lower() == '.parquet':
            frame = pd.read_parquet(BytesIO(original))
        else:
            raise ValueError('Local source must be CSV or Parquet')
        from dataclasses import asdict
        request = {'original_name': path.name, 'instrument': {**asdict(instrument),
            'asset_class': instrument.asset_class.value}, 'timeframe': timeframe.value,
            'source_timezone': source_timezone, 'timestamp_semantics': semantics.value}
        return ProviderSnapshot({'bars': frame, 'original': original, 'request': request},
            {'bars': frame.copy(deep=True), 'request': request}, self.version,
            ['Local file supplied by the researcher; supplier accuracy and completeness are not independently verified.',
             'No sorting, filling, deduplication or repair at the local normalization boundary.'])
