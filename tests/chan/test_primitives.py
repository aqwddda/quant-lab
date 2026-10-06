from datetime import datetime, timedelta, timezone
import pytest
from src.market import Bar, Timeframe
from src.chan import InclusionProcessor, ChanConfig, Direction, FractalType, FractalDetector


def bar(i,high,low):
    return Bar(datetime(2020,1,1,tzinfo=timezone.utc)+timedelta(minutes=i),
        'EURUSD',(high+low)/2,high,low,(high+low)/2,timeframe=Timeframe.M1)


def merged(ranges,policy='error'):
    processor=InclusionProcessor(ChanConfig(policy))
    for i,(high,low) in enumerate(ranges): processor.update(bar(i,high,low))
    return processor


@pytest.mark.parametrize('ranges,direction', [([(3,1),(4,2)],Direction.UP), ([(4,2),(3,1)],Direction.DOWN)])
def test_noncontaining(ranges,direction):
    result=merged(ranges).merged_bars
    assert len(result)==2
    assert result[-1].direction==direction


@pytest.mark.parametrize('ranges,expected', [([(3,1),(5,2),(4,3)],(5,3)),
    ([(3,1),(5,2),(6,1)],(6,2)), ([(6,4),(5,2),(4,3)],(4,2)),
    ([(6,4),(5,2),(6,1)],(5,1))])
def test_containment_direction(ranges,expected):
    result=merged(ranges).merged_bars
    assert len(result)==2
    assert (result[-1].high,result[-1].low)==expected
    assert result[-1].raw_indices==(1,2)
    assert result[-1].start_timestamp==bar(1,*ranges[1]).timestamp
    assert result[-1].end_timestamp==bar(2,*ranges[2]).timestamp


def test_sequential_merge_uses_merged_range():
    # After UP merge (5,2)+(4,3) -> (5,3), (4.5,2.5) is DOWN.
    # Comparing the old raw (4,3) would erroneously treat it as containment.
    result=merged([(3,1),(5,2),(4,3),(4.5,2.5)]).merged_bars
    assert len(result)==3
    assert result[-1].direction==Direction.DOWN
    assert result[-2].raw_indices==(1,2)


def test_initial_policy_error_and_explicit():
    with pytest.raises(ValueError,match='Initial inclusion'): merged([(5,1),(4,2)])
    assert merged([(5,1),(4,2)],'up').merged_bars[0].low==2
    assert merged([(5,1),(4,2)],'down').merged_bars[0].high==4


@pytest.mark.parametrize('ranges,kind',[([(3,1),(4,2),(3,1)],FractalType.TOP),
    ([(4,2),(3,1),(4,2)],FractalType.BOTTOM), ([(3,1),(4,2),(5,3)],None),
    ([(5,3),(4,2),(3,1)],None)])
def test_fractal_direction_and_availability(ranges,kind):
    result=merged(ranges).merged_bars
    fractal=FractalDetector().detect(*result)
    if kind is None: assert fractal is None
    else:
        assert fractal.type==kind
        assert fractal.pivot_time==bar(1,*ranges[1]).timestamp
        assert fractal.confirmed_at==bar(2,*ranges[2]).available_at
        assert fractal.confirmed_at>fractal.pivot_time


@pytest.mark.parametrize('highlow',[(4,1),(3,2)])
def test_equal_extreme_is_not_fractal(highlow):
    from dataclasses import replace
    triple=merged([(3,1),(4,2),(3,1)]).merged_bars
    triple=(*triple[:2],replace(triple[2],high=highlow[0],low=highlow[1]))
    assert FractalDetector().detect(*triple) is None


def test_overlapping_triples_allowed():
    result=merged([(3,1),(4,2),(3,1),(4,2)]).merged_bars
    detector=FractalDetector()
    assert detector.detect(*result[:3]).type==FractalType.TOP
    assert detector.detect(*result[1:]).type==FractalType.BOTTOM
