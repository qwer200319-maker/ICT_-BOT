from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

import config
from strategy.market_bias import find_swings


@dataclass
class CHOCHSignal:
    direction: str  # "bullish" or "bearish"
    level: float
    candle_index: int


def confirm_choch(
    df: pd.DataFrame,
    direction: str,
    lookback: int = config.SWING_LOOKBACK,
) -> Optional[CHOCHSignal]:
    """
    Confirm change of character (CHOCH) after a sweep.
    Bullish CHOCH: break of recent swing high.
    Bearish CHOCH: break of recent swing low.
    """
    if df is None or df.empty:
        return None

    highs, lows = find_swings(df, lookback)
    if len(highs) < 2 or len(lows) < 2:
        return None

    last_close = df["close"].iloc[-1]
    idx = len(df) - 1

    if direction == "bullish":
        prev_high = highs[-2][1]
        last_high = highs[-1][1]
        if last_high < prev_high and last_close > last_high:
            return CHOCHSignal(direction="bullish", level=last_high, candle_index=idx)

    if direction == "bearish":
        prev_low = lows[-2][1]
        last_low = lows[-1][1]
        if last_low > prev_low and last_close < last_low:
            return CHOCHSignal(direction="bearish", level=last_low, candle_index=idx)

    return None
