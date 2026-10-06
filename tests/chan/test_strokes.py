from dataclasses import replace
from datetime import datetime, timedelta, timezone
import pytest
from src.market import Bar, Timeframe
from src.chan import ChanAnalyzer, StrokeStatus, FractalType, Direction
from src.chan.stroke import assert_stroke_extremes


def bars(values):
    return [Bar(datetime(2020,1,1,tzinfo=timezone.utc)+timedelta(minutes=i),'EURUSD',
        x+1,x+2,x,x+1,timeframe=Timeframe.M1) for i,x in enumerate(values)]


def analyze(values):
    return ChanAnalyzer().extend(bars(values))


def test_valid_one_stroke_and_reverse_confirmation():
    analyzer=analyze([3,1,3,4,5,7,5])
    assert len(analyzer.strokes)==1
    first=analyzer.current_stroke
    assert first.direction==Direction.UP
    assert first.status==StrokeStatus.TENTATIVE
    assert first.start.center.index==1
    assert first.end.center.index==5
    analyzer.extend(bars([3,1,3,4,5,7,5,4,3,1,3])[7:])
    assert len(analyzer.strokes)==2
    assert analyzer.confirmed_strokes[0].status==StrokeStatus.CONFIRMED
    assert analyzer.current_stroke.direction==Direction.DOWN
    assert analyzer.confirmed_strokes[0].confirmed_at==analyzer.fractals[-1].confirmed_at
    assert first.status==StrokeStatus.TENTATIVE  # old snapshot was never mutated


def test_distance_three_invalid_and_four_valid():
    assert not analyze([3,1,3,5,7,5]).strokes
    assert len(analyze([3,1,3,4,5,7,5]).strokes)==1


def test_higher_top_replaces_end_lower_top_ignored():
    analyzer=analyze([3,1,3,4,5,7,5,6,9,6])
    assert len(analyzer.strokes)==1
    assert analyzer.current_stroke.end.center.index==8
    analyzer=analyze([3,1,3,4,5,9,5,6,7,6])
    assert len(analyzer.strokes)==1
    assert analyzer.current_stroke.end.center.index==5


def test_lower_bottom_replaces_end_higher_bottom_ignored():
    analyzer=analyze([8,10,8,7,6,4,6,5,2,5])
    assert len(analyzer.strokes)==1
    assert analyzer.current_stroke.end.center.index==8
    analyzer=analyze([8,10,8,7,6,2,6,5,4,5])
    assert analyzer.current_stroke.end.center.index==5


def test_extreme_invariant_is_explicit():
    analyzer=analyze([3,1,3,4,5,7,5])
    stroke=analyzer.current_stroke
    bad=replace(stroke,start=replace(stroke.start,price=2))
    with pytest.raises(ValueError,match='invariant'):
        assert_stroke_extremes(bad,analyzer.merged_bars)


def test_equal_endpoint_keeps_first_provisional_rule():
    analyzer=analyze([3,1,3,4,5,7,5,6,7,6])
    assert analyzer.current_stroke.end.center.index==5


def test_gap_does_not_add_merged_distance():
    analyzer=analyze([5,1,5,20,30,20])
    assert not analyzer.strokes


def test_confirmed_prefix_and_future_mutation():
    sequence=[3,1,3,4,5,7,5,4,3,1,3,4,5,7,5,4]
    history=bars(sequence*63)
    analyzer=ChanAnalyzer().extend(history[:100])
    fractals,confirmed=analyzer.fractals,analyzer.confirmed_strokes
    assert confirmed
    cutoff=history[99].available_at
    analyzer.extend(history[100:1000])
    assert tuple(f for f in analyzer.fractals if f.confirmed_at<=cutoff)==fractals
    assert tuple(s for s in analyzer.confirmed_strokes if s.confirmed_at<=cutoff)==confirmed
    mutated=[*history[:100],*[replace(b,open=b.open*10,high=b.high*10,low=b.low*10,close=b.close*10) for b in history[100:1000]]]
    other=ChanAnalyzer().extend(mutated)
    assert tuple(f for f in other.fractals if f.confirmed_at<=cutoff)==fractals
    assert tuple(s for s in other.confirmed_strokes if s.confirmed_at<=cutoff)==confirmed
    assert isinstance(analyzer.raw_bars,tuple)
    with pytest.raises(Exception): analyzer.confirmed_strokes[0].end.price=100


def test_future_inclusion_preserves_as_known_right_snapshot():
    from dataclasses import replace
    history=bars([3,1,3])
    analyzer=ChanAnalyzer().extend(history)
    fractal=analyzer.fractals[0]
    # Current right UP range [5,3] contains [4.5,3.5], so its low changes.
    later=replace(history[-1],timestamp=history[-1].available_at,open=4.,high=4.5,low=3.5,close=4.)
    analyzer.update(later)
    assert analyzer.fractals==(fractal,)
    assert analyzer.merged_bars[-1].low==3.5
    assert fractal.right.low==3
    assert fractal.right.raw_indices==(2,)
