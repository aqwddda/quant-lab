"""Normalize explicit local timestamp semantics; preserve unknown optional data."""
import pandas as pd
from quant_lab.market import Timeframe, TimestampSemantics
from quant_lab.data.schema import V3_BAR_COLUMNS, V3_OPTIONAL_COLUMNS, require_columns
from quant_lab.data.validation import validate_bars_v3


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
    columns = V3_BAR_COLUMNS + [name for name in V3_OPTIONAL_COLUMNS if name in frame]
    frame = frame[columns]
    validate_bars_v3(frame, timeframe)
    return frame
