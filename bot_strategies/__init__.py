from .strategies import *
from typing import Dict, Callable


def _composite_strategy_buy(df:pd.DataFrame) -> bool:
    return (
        Engulf.is_bullish_engulf(df) or 
        Rejection.is_bullish_rejection(df)
    )

def _composite_strategy_sell(df:pd.DataFrame) -> bool:
    return (
        Engulf.is_bearish_engulf(df) or
        Rejection.is_bearish_rejection(df)
    )

__strategies__: Dict[str, Dict[str, Callable]] = {
    "engulf": {'buy': Engulf.is_bullish_engulf, 'sell': Engulf.is_bearish_engulf},
    "rejection": {'buy': Rejection.is_bullish_rejection, 'sell': Rejection.is_bearish_rejection},
    "composite": {'buy': _composite_strategy_buy, 'sell': _composite_strategy_sell}
}