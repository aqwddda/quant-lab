import json
from copy import deepcopy
import pandas as pd
import pytest
from src.data.inspection import write_chan_outputs


def snapshot(analyzer):
    return deepcopy((analyzer.raw_bars, analyzer.merged_bars, analyzer.fractals,
        analyzer.strokes, analyzer.confirmed_strokes, analyzer.current_stroke))


def test_inspection_exports_all_files_and_known_times(analyzer, tmp_path):
    before = snapshot(analyzer)
    counts = write_chan_outputs(analyzer, tmp_path, plot=True, audit={'dataset_id': 'golden_fixture'})
    assert counts == {'raw_bars': 15, 'merged_bars': 15, 'fractals': 4, 'strokes': 3}
    for name in ['raw_bars.csv', 'merged_bars.csv', 'fractals.csv', 'strokes.csv', 'chan.json',
        '01_raw_candles.png', '02_merged_bars.png', '03_chan_structure.png',
        '04_raw_with_chan_overlay.png', '05_summary.txt']:
        assert (tmp_path/name).stat().st_size > 0
    raw = pd.read_csv(tmp_path/'raw_bars.csv')
    assert {'volume', 'tick_volume', 'amount', 'open_interest', 'available_at'}.issubset(raw)
    assert raw.volume.isna().all()
    assert pd.Timestamp(raw.available_at.iloc[0]) == analyzer.raw_bars[0].available_at
    merged = pd.read_csv(tmp_path/'merged_bars.csv')
    assert merged.raw_count.tolist() == [len(bar.raw_indices) for bar in analyzer.merged_bars]
    report = json.loads((tmp_path/'chan.json').read_text())
    assert report['audit']['dataset_id'] == 'golden_fixture'
    for item, fractal in zip(report['fractals'], analyzer.fractals):
        assert item['pivot_time'] == fractal.pivot_time.isoformat()
        assert item['confirmed_at'] == fractal.confirmed_at.isoformat()
        assert item['center_raw_indices'] == list(fractal.center.raw_indices)
        assert item['price'] == fractal.price
    assert report['strokes'][-1]['status'] == 'tentative'
    assert report['strokes'][-1]['confirmed_at'] is None
    summary = (tmp_path/'05_summary.txt').read_text()
    assert 'confirmed stroke count: 2' in summary
    assert 'tentative stroke exists: True' in summary
    assert snapshot(analyzer) == before


@pytest.mark.parametrize('export_csv,export_json', [(True, False), (False, True), (False, False)])
def test_export_options(analyzer, tmp_path, export_csv, export_json):
    write_chan_outputs(analyzer, tmp_path, export_csv=export_csv, export_json=export_json)
    assert (tmp_path/'raw_bars.csv').exists() == export_csv
    assert (tmp_path/'chan.json').exists() == export_json
    assert not list(tmp_path.glob('*.png'))


def test_inclusion_export_retains_multiple_raw_indices(tmp_path):
    from datetime import datetime, timedelta, timezone
    from pathlib import Path
    from src.chan import ChanAnalyzer
    from src.market import Bar, Timeframe
    fixture = json.loads((Path(__file__).resolve().parents[1] /
        'fixtures/chan/sequential_inclusion.json').read_text())
    analyzer = ChanAnalyzer().extend([
        Bar(datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=i),
            'EURUSD', (high+low)/2, high, low, (high+low)/2, timeframe=Timeframe.M1)
        for i, (high, low) in enumerate(fixture['raw_ranges'])])
    write_chan_outputs(analyzer, tmp_path)
    report = json.loads((tmp_path/'chan.json').read_text())
    merged = report['merged_bars'][1]
    assert merged['raw_indices'] == [1, 2]
    assert merged['raw_count'] == 2
    assert [merged['high'], merged['low']] == [5, 3]
    assert merged['end_timestamp'] == analyzer.raw_bars[2].timestamp.isoformat()
