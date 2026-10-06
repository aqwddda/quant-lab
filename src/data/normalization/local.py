"""Normalize explicit local timestamp semantics; preserve unknown optional data."""
import pandas as pd
from src.market import Timeframe, TimestampSemantics
from src.data.schema import BAR_COLUMNS, OPTIONAL_BAR_COLUMNS, require_columns
from src.data.validation import validate_bars


def normalize_local(prepared):
    request = prepared['request']
    instrument = request['instrument']
    timeframe = Timeframe.parse(request['timeframe'])
    frame = prepared['bars'].copy(deep=True)
    require_columns(frame, ['timestamp', 'open', 'high', 'low', 'close'])
    if 'symbol' in frame and not frame.symbol.eq(instrument['provider_symbol']).all():
        raise ValueError('Local source symbol must match provider_symbol')
    frame['symbol'] = instrument['symbol']
    dates = pd.to_datetime(frame.timestamp, errors='raise')
    if dates.dt.tz is None:
        dates = dates.dt.tz_localize(request['source_timezone'], ambiguous='raise', nonexistent='raise')
    else:
        from zoneinfo import ZoneInfo
        zone = ZoneInfo(request['source_timezone'])
        if any(stamp.utcoffset() != stamp.to_pydatetime().astimezone(zone).utcoffset() for stamp in dates):
            raise ValueError('Aware source offsets do not match declared source_timezone')
    dates = dates.dt.tz_convert('UTC')
    if TimestampSemantics(request['timestamp_semantics']) == TimestampSemantics.BAR_END:
        dates = dates - timeframe.duration
    frame['timestamp'] = dates
    columns = BAR_COLUMNS + [name for name in OPTIONAL_BAR_COLUMNS if name in frame]
    frame = frame[columns]
    validate_bars(frame, timeframe)
    return frame
