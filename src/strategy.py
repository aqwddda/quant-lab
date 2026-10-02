"""Close-only indicators; targets become available after the row's close."""
import pandas as pd


def calculate_signals(data: pd.DataFrame, fast_window: int, slow_window: int) -> pd.DataFrame:
    if (type(fast_window) is not int or type(slow_window) is not int
            or not 0 < fast_window < slow_window):
        raise ValueError('Require integer windows: 0 < fast_window < slow_window')
    close = data['close']
    result = pd.DataFrame(index=data.index)
    result['fast_ma'] = close.rolling(fast_window, min_periods=fast_window).mean()
    result['slow_ma'] = close.rolling(slow_window, min_periods=slow_window).mean()
    result['target'] = (result.fast_ma > result.slow_ma).astype(int)
    result.loc[result.slow_ma.isna(), 'target'] = -1  # unavailable, rather than cash signal
    return result
