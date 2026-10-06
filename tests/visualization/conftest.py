from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import pytest
from src.chan import ChanAnalyzer
from src.market import Bar, Timeframe


@pytest.fixture
def analyzer():
    fixture = json.loads((Path(__file__).resolve().parents[1] /
        'fixtures/chan/alternating_strokes.json').read_text())
    bars = [Bar(datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=i),
        'EURUSD', low+.5 if i % 2 else high-.5, high, low,
        high-.5 if i % 2 else low+.5, timeframe=Timeframe.M1)
        for i, (high, low) in enumerate(fixture['raw_ranges'])]
    return ChanAnalyzer().extend(bars)
