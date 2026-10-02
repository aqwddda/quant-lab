import json
import pandas as pd
import pytest
from scripts.download_data import download_data
from src.data_loader import file_sha256


def test_adjusted_download_inclusive_end_and_frozen_file(monkeypatch, tmp_path):
    calls = {}

    class FakeTicker:
        def __init__(self, symbol):
            assert symbol == 'SPY'

        def history(self, **kwargs):
            calls.update(kwargs)
            return pd.DataFrame({
                'Open': [100., 101.], 'High': [102., 103.], 'Low': [99., 100.],
                'Close': [101., 102.], 'Volume': [1000, 2000],
            }, index=pd.date_range('2025-12-30', periods=2, tz='America/New_York', name='Date'))

    monkeypatch.setattr('scripts.download_data.yf.Ticker', FakeTicker)
    monkeypatch.setattr('scripts.download_data.yf.set_tz_cache_location', lambda path: None)
    output = tmp_path / 'spy.parquet'
    download_data(output, '2025-12-30', '2025-12-31')
    assert calls['end'] == '2026-01-01'
    assert calls['auto_adjust'] is True
    assert calls['repair'] is False
    data = pd.read_parquet(output)
    assert data.date.dt.tz is None
    assert data.date.iloc[-1] == pd.Timestamp('2025-12-31')
    original_hash = file_sha256(output)
    metadata = json.loads(output.with_suffix('.metadata.json').read_text())
    assert metadata['sha256'] == original_hash
    with pytest.raises(FileExistsError):
        download_data(output, '2025-12-30', '2025-12-31')
    assert file_sha256(output) == original_hash
