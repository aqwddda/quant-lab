"""Read frozen local Parquet only. Network access lives in the download script."""
from pathlib import Path
import hashlib
import pandas as pd
from src.validation import validate_market_data


def file_sha256(path) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load_market_data(path, start_date, end_date) -> pd.DataFrame:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f'Frozen dataset missing: {path}. Run scripts/download_data.py separately.')
    data = pd.read_parquet(path)
    validate_market_data(data)
    start, end = pd.Timestamp(start_date), pd.Timestamp(end_date)
    if start > end:
        raise ValueError('start_date must not exceed end_date')
    selected = data.loc[data.date.between(start, end)].reset_index(drop=True)
    validate_market_data(selected)
    return selected
