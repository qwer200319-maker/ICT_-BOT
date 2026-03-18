from __future__ import annotations

from typing import List, Tuple, Optional

import pandas as pd

import config

Swing = Tuple[int, float]


def find_swings(df: pd.DataFrame, lookback: int) -> tuple[List[Swing], List[Swing]]:
    """
    Identify swing highs and lows using a simple lookback window.
    Returns lists of (index, price).
    """
    highs: List[Swing] = []
    lows: List[Swing] = []

    if df is None or df.empty or len(df) < lookback * 2 + 1:
        return highs, lows

    highs_series = df["high"].values
    lows_series = df["low"].values

    for i in range(lookback, len(df) - lookback):
        high_window = highs_series[i - lookback : i + lookback + 1]
        low_window = lows_series[i - lookback : i + lookback + 1]

        if highs_series[i] == high_window.max():
            highs.append((i, highs_series[i]))
        if lows_series[i] == low_window.min():
            lows.append((i, lows_series[i]))

    return highs, lows


def detect_market_bias(
    df: pd.DataFrame, lookback: int = config.SWING_LOOKBACK
) -> Optional[str]:
    """
    Detect bullish/bearish bias using higher highs/lows on HTF.
    Returns "bullish", "bearish", or None.
    """
    highs, lows = find_swings(df, lookback)
    if len(highs) < 2 or len(lows) < 2:
        return None

    last_high_1, last_high_2 = highs[-2][1], highs[-1][1]
    last_low_1, last_low_2 = lows[-2][1], lows[-1][1]

    if last_high_2 > last_high_1 and last_low_2 > last_low_1:
        return "bullish"
    if last_high_2 < last_high_1 and last_low_2 < last_low_1:
        return "bearish"
    return None
