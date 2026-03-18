from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd

import config


@dataclass
class FVGZone:
    direction: str  # "bullish" or "bearish"
    lower: float
    upper: float
    index: int


def detect_fvgs(
    df: pd.DataFrame, max_age_bars: int = config.FVG_MAX_AGE_BARS
) -> List[FVGZone]:
    """
    Detect 3-candle fair value gaps (FVG).
    Bullish FVG: Candle1 high < Candle3 low.
    Bearish FVG: Candle1 low > Candle3 high.
    """
    zones: List[FVGZone] = []
    if df is None or df.empty or len(df) < 3:
        return zones

    start = max(2, len(df) - max_age_bars) if max_age_bars else 2

    for i in range(start, len(df)):
        c1 = df.iloc[i - 2]
        c3 = df.iloc[i]

        if c1["high"] < c3["low"]:
            zones.append(
                FVGZone(
                    direction="bullish",
                    lower=c1["high"],
                    upper=c3["low"],
                    index=i,
                )
            )
        elif c1["low"] > c3["high"]:
            zones.append(
                FVGZone(
                    direction="bearish",
                    lower=c3["high"],
                    upper=c1["low"],
                    index=i,
                )
            )

    return zones
