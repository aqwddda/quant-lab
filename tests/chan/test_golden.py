from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import pytest
from quant_lab.market import Bar, Timeframe
from quant_lab.chan import ChanAnalyzer


@pytest.mark.parametrize('name',['alternating_strokes','sequential_inclusion'])
def test_human_marked_golden(name):
    fixture=json.loads((Path(__file__).resolve().parents[1]/'fixtures/chan'/f'{name}.json').read_text())
    raw=[Bar(datetime(2020,1,1,tzinfo=timezone.utc)+timedelta(minutes=i),'EURUSD',
        (high+low)/2,high,low,(high+low)/2,timeframe=Timeframe.M1)
        for i,(high,low) in enumerate(fixture['raw_ranges'])]
    analyzer=ChanAnalyzer().extend(raw)
    assert [[b.high,b.low,list(b.raw_indices)] for b in analyzer.merged_bars]==fixture['expected_merged']
    confirmations={b.available_at:i for i,b in enumerate(raw)}
    assert [[f.type.value,f.center.index,f.price,confirmations[f.confirmed_at]]
        for f in analyzer.fractals]==fixture['expected_fractals']
    assert [[s.start.center.index,s.end.center.index,s.direction.value,s.status.value,
        confirmations[s.confirmed_at] if s.confirmed_at is not None else None]
        for s in analyzer.strokes]==fixture['expected_strokes']
