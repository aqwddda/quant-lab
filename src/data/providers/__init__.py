"""Registry is imported by download code only; SDK imports are lazy."""
from src.data.providers.yahoo import YahooProvider
from src.data.providers.tushare import TushareProvider

from src.data.providers.local import LocalBarProvider

PROVIDERS = {'yahoo': YahooProvider, 'tushare': TushareProvider, 'local': LocalBarProvider}


def get_provider(name, **kwargs):
    # Keep optional SDKs outside the local loader/backtest dependency graph.
    if name not in PROVIDERS:
        raise ValueError(f'Unknown provider: {name}')
    return PROVIDERS[name](**kwargs)
