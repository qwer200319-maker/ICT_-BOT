from __future__ import annotations

import pandas as pd

import config


def _true_range(df: pd.DataFrame) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"].shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - close).abs(), (low - close).abs()], axis=1
    ).max(axis=1)
    return tr


def atr_percent(
    df: pd.DataFrame, period: int = config.ATR_PERIOD
) -> float:
    """
    Compute ATR as a percent of the last close.
    """
    if df is None or df.empty or len(df) < period + 1:
        return 0.0

    tr = _true_range(df)
    atr = tr.rolling(window=period, min_periods=period).mean().iloc[-1]
    last_close = df["close"].iloc[-1]
    if last_close <= 0:
        return 0.0
    return (atr / last_close) * 100


def passes_atr_filter(
    df: pd.DataFrame,
    enabled: bool = config.ATR_FILTER_ENABLED,
    min_pct: float = config.ATR_MIN_PCT,
    period: int = config.ATR_PERIOD,
) -> bool:
    if not enabled:
        return True
    return atr_percent(df, period=period) >= min_pct
