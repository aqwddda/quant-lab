import pytest
from src.data.validation import validate_bars


def test_canonical_schema(canonical):
    validate_bars(canonical)
    # Provider float volumes are valid if mathematically integral.
    canonical['volume'] = canonical.volume.astype(float)
    validate_bars(canonical)


@pytest.mark.parametrize('column', ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume'])
def test_missing_column(canonical, column):
    with pytest.raises(ValueError, match='Schema'):
        validate_bars(canonical.drop(columns=column))


@pytest.mark.parametrize('symbol', ['', ' AAPL', None, 10])
def test_invalid_symbol(canonical, symbol):
    canonical['symbol'] = symbol
    with pytest.raises(ValueError):
        validate_bars(canonical)
