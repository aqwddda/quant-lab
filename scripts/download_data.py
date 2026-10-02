"""Explicit one-time adjusted SPY download. Never overwrite a frozen dataset."""
import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
import yfinance as yf
from src.data_loader import file_sha256
from src.validation import validate_market_data


def download_data(output: Path, start: str, end: str):
    metadata_path = output.with_suffix('.metadata.json')
    if output.exists() or metadata_path.exists():
        raise FileExistsError(f'Refusing to overwrite frozen data: {output}')
    start_date, end_date = date.fromisoformat(start), date.fromisoformat(end)
    if start_date > end_date:
        raise ValueError('start must not exceed end')
    output.parent.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(ROOT / '.cache' / 'yfinance'))
    # Yahoo's end is exclusive. Convert timestamps to New York session labels
    # BEFORE stripping timezone; converting to UTC first can change the label.
    history = yf.Ticker('SPY').history(
        start=start, end=(end_date + timedelta(days=1)).isoformat(), interval='1d',
        auto_adjust=True, back_adjust=False, repair=False, actions=False,
        keepna=True, raise_errors=True,
    )
    if history.empty:
        raise ValueError('Provider returned no data')
    index = pd.DatetimeIndex(history.index)
    if index.tz is None:
        raise ValueError('Provider timestamps lack exchange timezone')
    history.index = index.tz_convert('America/New_York').tz_localize(None).normalize()
    data = history.rename(columns=str.lower).reset_index().rename(columns={'Date': 'date', 'index': 'date'})
    data = data[['date', 'open', 'high', 'low', 'close', 'volume']]
    validate_market_data(data)
    if not data.date.between(pd.Timestamp(start), pd.Timestamp(end)).all():
        raise ValueError('Provider returned out-of-range dates')
    # Write exclusively; existing experiments cannot be silently replaced.
    with output.open('xb') as handle:
        data.to_parquet(handle, index=False, engine='pyarrow')
    metadata = {
        'symbol': 'SPY', 'provider': 'Yahoo Finance via yfinance',
        'yfinance_version': yf.__version__, 'auto_adjust': True, 'repair': False,
        'requested_start': start, 'requested_end_inclusive': end,
        'actual_start': data.date.iloc[0].date().isoformat(),
        'actual_end': data.date.iloc[-1].date().isoformat(), 'rows': len(data),
        'date_semantics': 'timezone-naive America/New_York exchange session date',
        'downloaded_at_utc': datetime.now(timezone.utc).isoformat(),
        'sha256': file_sha256(output),
    }
    with metadata_path.open('x') as handle:
        json.dump(metadata, handle, indent=2, allow_nan=False)
    print(json.dumps(metadata, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', default='2015-01-01')
    parser.add_argument('--end', default='2025-12-31')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/raw/spy_daily.parquet')
    args = parser.parse_args()
    download_data(args.output, args.start, args.end)


if __name__ == '__main__':
    main()
