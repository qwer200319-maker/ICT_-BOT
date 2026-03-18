from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

import config
from strategy.market_bias import find_swings


@dataclass
class LiquidityPool:
    level: float
    kind: str  # "high" or "low"


@dataclass
class LiquiditySweep:
    direction: str  # "bullish" or "bearish"
    level: float
    candle_index: int


def _is_equal(a: float, b: float, tolerance: float) -> bool:
    if a == 0:
        return False
    return abs(a - b) / a <= tolerance


def detect_liquidity_pools(
    df: pd.DataFrame,
    lookback: int = config.SWING_LOOKBACK,
    tolerance: float = config.EQUALITY_TOLERANCE,
) -> List[LiquidityPool]:
    """
    Detect equal highs/lows and recent swing highs/lows as liquidity pools.
    """
    pools: List[LiquidityPool] = []
    highs, lows = find_swings(df, lookback)

    # Equal highs
    for i in range(len(highs) - 1):
        level_a = highs[i][1]
        level_b = highs[i + 1][1]
        if _is_equal(level_a, level_b, tolerance):
            pools.append(LiquidityPool(level=(level_a + level_b) / 2, kind="high"))

    # Equal lows
    for i in range(len(lows) - 1):
        level_a = lows[i][1]
        level_b = lows[i + 1][1]
        if _is_equal(level_a, level_b, tolerance):
            pools.append(LiquidityPool(level=(level_a + level_b) / 2, kind="low"))

    # Include most recent swing high/low as liquidity
    if highs:
        pools.append(LiquidityPool(level=highs[-1][1], kind="high"))
    if lows:
        pools.append(LiquidityPool(level=lows[-1][1], kind="low"))

    return pools


def detect_liquidity_sweep(
    df: pd.DataFrame, pools: List[LiquidityPool], lookback_bars: int = config.SWEEP_LOOKBACK_BARS
) -> Optional[LiquiditySweep]:
    """
    Detect a sweep on the most recent closed candle.
    Bearish sweep: price breaks above highs then closes below.
    Bullish sweep: price breaks below lows then closes above.
    """
    if df is None or df.empty or not pools:
        return None

    idx = len(df) - 1
    candle = df.iloc[idx]

    recent_pools = pools[-lookback_bars:] if len(pools) > lookback_bars else pools

    for pool in reversed(recent_pools):
        if pool.kind == "high":
            if candle["high"] > pool.level and candle["close"] < pool.level:
                return LiquiditySweep(direction="bearish", level=pool.level, candle_index=idx)
        if pool.kind == "low":
            if candle["low"] < pool.level and candle["close"] > pool.level:
                return LiquiditySweep(direction="bullish", level=pool.level, candle_index=idx)

    return None
