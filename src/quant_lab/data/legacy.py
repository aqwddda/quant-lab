"""V1 compatibility API. The only reading implementation lives in data.loader."""
from pathlib import Path
import json
from quant_lab.data.manifest import file_sha256
from quant_lab.data.loader import load_bars


def load_market_data(path, start_date, end_date):
    path = Path(path)
    sidecar = path.with_suffix('.metadata.json')
    symbol = json.loads(sidecar.read_text())['symbol'] if sidecar.exists() else '_legacy_'
    data = load_bars('US', [symbol], start_date, end_date, price_basis='legacy_provider_adjusted',
                     legacy_path=path, require_legacy_metadata=False)
    result = data.drop(columns='symbol')
    result['date'] = result.date.astype(data.attrs['_legacy_date_dtype'])
    result.attrs.clear()
    return result
