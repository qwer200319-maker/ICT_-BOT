import logging
import re
from typing import Optional, List

import numpy as np
import pandas as pd
import requests

import config

logger = logging.getLogger(__name__)


def _interval_to_pandas_freq(interval: str) -> str:
    match = re.match(r"(\d+)([mhd])", interval)
    if not match:
        return "1min"
    value, unit = match.groups()
    if unit == "m":
        return f"{value}min"
    if unit == "h":
        return f"{value}H"
    if unit == "d":
        return f"{value}D"
    return "1min"


def _generate_mock_candles(interval: str, limit: int) -> pd.DataFrame:
    freq = _interval_to_pandas_freq(interval)
    times = pd.date_range(end=pd.Timestamp.utcnow(), periods=limit, freq=freq)

    prices = [config.MOCK_START_PRICE]
    for _ in range(limit - 1):
        change = np.random.normal(0, config.MOCK_VOLATILITY)
        prices.append(prices[-1] * (1 + change))

    prices = np.array(prices)
    highs = prices * (1 + np.random.uniform(0.0005, 0.003, size=limit))
    lows = prices * (1 - np.random.uniform(0.0005, 0.003, size=limit))
    opens = np.r_[prices[0], prices[:-1]]
    closes = prices
    volume = np.random.uniform(10, 100, size=limit)

    df = pd.DataFrame(
        {
            "time": times,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volume,
        }
    )
    return df


def _get_base_urls() -> List[str]:
    if getattr(config, "USE_FALLBACK_ENDPOINTS", False) and getattr(
        config, "EXCHANGE_BASE_URLS", None
    ):
        return list(config.EXCHANGE_BASE_URLS)
    return [config.EXCHANGE_BASE_URL]


def fetch_candles(
    symbol: str,
    interval: str,
    limit: int,
    base_url: str = config.EXCHANGE_BASE_URL,
    endpoint: str = config.KLINES_ENDPOINT,
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV candles from the configured exchange.
    Returns a DataFrame with columns: time, open, high, low, close, volume.
    """
    if config.USE_MOCK_DATA:
        return _generate_mock_candles(interval, limit)

    base_urls = _get_base_urls()
    for url_base in base_urls:
        url = f"{url_base}{endpoint}"
        params = {"symbol": symbol, "interval": interval, "limit": limit}

        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.warning("Failed to fetch candles for %s %s from %s: %s", symbol, interval, url_base, exc)
            continue

        if not isinstance(data, list) or not data:
            logger.warning("Empty candle data for %s %s from %s", symbol, interval, url_base)
            continue

        df = pd.DataFrame(
            data,
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_asset_volume",
                "trades",
                "taker_buy_base",
                "taker_buy_quote",
                "ignore",
            ],
        )

        df = df[["open_time", "open", "high", "low", "close", "volume"]].copy()
        df["time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df[["open", "high", "low", "close", "volume"]] = df[
            ["open", "high", "low", "close", "volume"]
        ].astype(float)
        df = df.drop(columns=["open_time"])
        df = df.reset_index(drop=True)

        return df

    return None
