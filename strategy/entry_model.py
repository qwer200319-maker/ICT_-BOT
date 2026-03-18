from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd

import config
from risk.risk_manager import calculate_rr
from strategy.choch_detector import CHOCHSignal
from strategy.fvg_detector import FVGZone
from strategy.liquidity_detector import LiquidityPool, LiquiditySweep


@dataclass
class TradeSignal:
    pair: str
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    reason: str
    timestamp: datetime


def _find_retrace_fvg(
    fvgs: List[FVGZone], direction: str, current_price: float
) -> Optional[FVGZone]:
    candidates = [z for z in fvgs if z.direction == direction]
    for zone in reversed(candidates):
        if zone.lower <= current_price <= zone.upper:
            return zone
    return None


def _next_liquidity_target(
    pools: List[LiquidityPool], direction: str, entry: float
) -> Optional[float]:
    if not pools:
        return None

    if direction == "long":
        highs = sorted({p.level for p in pools if p.kind == "high"})
        for level in highs:
            if level > entry:
                return level
    else:
        lows = sorted({p.level for p in pools if p.kind == "low"})
        for level in reversed(lows):
            if level < entry:
                return level

    return None


def generate_signal(
    pair: str,
    bias: str,
    sweep: LiquiditySweep,
    choch: CHOCHSignal,
    fvgs: List[FVGZone],
    entry_df: pd.DataFrame,
    pools: List[LiquidityPool],
) -> Optional[TradeSignal]:
    if entry_df is None or entry_df.empty:
        return None

    current_price = float(entry_df["close"].iloc[-1])

    if bias == "bullish" and sweep.direction == "bullish" and choch.direction == "bullish":
        fvg = _find_retrace_fvg(fvgs, "bullish", current_price)
        if not fvg:
            return None
        entry = current_price
        stop = sweep.level - config.SL_BUFFER
        target = _next_liquidity_target(pools, "long", entry)
        if target is None:
            return None
        rr = calculate_rr(entry, stop, target)
        if rr < config.MIN_RISK_REWARD:
            return None
        reason = "Liquidity Sweep + CHOCH + FVG"
        return TradeSignal(
            pair=pair,
            direction="LONG",
            entry=entry,
            stop_loss=stop,
            take_profit=target,
            risk_reward=rr,
            reason=reason,
            timestamp=datetime.now(timezone.utc),
        )

    if bias == "bearish" and sweep.direction == "bearish" and choch.direction == "bearish":
        fvg = _find_retrace_fvg(fvgs, "bearish", current_price)
        if not fvg:
            return None
        entry = current_price
        stop = sweep.level + config.SL_BUFFER
        target = _next_liquidity_target(pools, "short", entry)
        if target is None:
            return None
        rr = calculate_rr(entry, stop, target)
        if rr < config.MIN_RISK_REWARD:
            return None
        reason = "Liquidity Sweep + CHOCH + FVG"
        return TradeSignal(
            pair=pair,
            direction="SHORT",
            entry=entry,
            stop_loss=stop,
            take_profit=target,
            risk_reward=rr,
            reason=reason,
            timestamp=datetime.now(timezone.utc),
        )

    return None
