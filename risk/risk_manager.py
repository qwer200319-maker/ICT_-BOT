from __future__ import annotations

import config


def calculate_rr(entry: float, stop: float, target: float) -> float:
    risk = abs(entry - stop)
    reward = abs(target - entry)
    if risk <= 0:
        return 0.0
    return reward / risk


def position_size(
    entry: float,
    stop: float,
    account_balance: float = config.ACCOUNT_BALANCE,
    risk_pct: float = config.RISK_PER_TRADE,
) -> float:
    """
    Calculate position size based on risk percentage.
    Returns size in units of the base asset.
    """
    risk_amount = account_balance * risk_pct
    risk_per_unit = abs(entry - stop)
    if risk_per_unit <= 0:
        return 0.0
    return risk_amount / risk_per_unit
