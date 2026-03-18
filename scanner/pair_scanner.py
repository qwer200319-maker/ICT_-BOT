from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd

import config
from data.fetch_candles import fetch_candles
from strategy.market_bias import detect_market_bias
from strategy.liquidity_detector import detect_liquidity_pools, detect_liquidity_sweep
from strategy.choch_detector import confirm_choch, CHOCHSignal
from strategy.fvg_detector import detect_fvgs, FVGZone
from strategy.entry_model import generate_signal, TradeSignal
from strategy.liquidity_detector import LiquidityPool, LiquiditySweep
from utils.volatility_filter import passes_atr_filter

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    pair: str
    htf_df: pd.DataFrame
    setup_df: pd.DataFrame
    entry_df: pd.DataFrame
    bias: Optional[str]
    pools: list[LiquidityPool]
    sweep: Optional[LiquiditySweep]
    choch: Optional[CHOCHSignal]
    fvgs: list[FVGZone]
    signal: Optional[TradeSignal]
    atr_ok: bool


def scan_pair(pair: str) -> Optional[ScanResult]:
    """
    Scan a single pair across HTF / setup / entry timeframes.
    """
    htf_df = fetch_candles(pair, config.TIMEFRAMES["htf"], config.CANDLE_LIMITS["htf"])
    setup_df = fetch_candles(
        pair, config.TIMEFRAMES["setup"], config.CANDLE_LIMITS["setup"]
    )
    entry_df = fetch_candles(
        pair, config.TIMEFRAMES["entry"], config.CANDLE_LIMITS["entry"]
    )

    if htf_df is None or setup_df is None or entry_df is None:
        return None

    atr_ok = passes_atr_filter(entry_df)
    bias = detect_market_bias(htf_df)
    pools = detect_liquidity_pools(setup_df)
    sweep = detect_liquidity_sweep(setup_df, pools)
    choch = confirm_choch(setup_df, direction=sweep.direction) if sweep else None
    fvgs = detect_fvgs(entry_df)

    signal = None
    if atr_ok and bias and sweep and choch:
        signal = generate_signal(
            pair=pair,
            bias=bias,
            sweep=sweep,
            choch=choch,
            fvgs=fvgs,
            entry_df=entry_df,
            pools=pools,
        )

    return ScanResult(
        pair=pair,
        htf_df=htf_df,
        setup_df=setup_df,
        entry_df=entry_df,
        bias=bias,
        pools=pools,
        sweep=sweep,
        choch=choch,
        fvgs=fvgs,
        signal=signal,
        atr_ok=atr_ok,
    )
