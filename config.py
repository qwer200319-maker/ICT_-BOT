"""
Global configuration for the ICT trading bot.
Update these values before running.
"""

import os


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y"}


# Exchange / data source
EXCHANGE_BASE_URL = os.getenv("EXCHANGE_BASE_URL", "https://api.binance.us")
KLINES_ENDPOINT = "/api/v3/klines"
API_KEY = os.getenv("API_KEY", "")
API_SECRET = os.getenv("API_SECRET", "")

# Optional fallback endpoints
USE_FALLBACK_ENDPOINTS = True
EXCHANGE_BASE_URLS = [
    "https://api.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api.binance.us",
]

# Mock data for UI/testing when APIs are blocked
USE_MOCK_DATA = _env_bool("USE_MOCK_DATA", False)
MOCK_START_PRICE = 30000.0
MOCK_VOLATILITY = 0.004  # 0.4% per candle

# Trading pairs and timeframes
PAIRS = ["BTCUSDT", "ETHUSDT"]
TIMEFRAMES = {
    "htf": "1h",     # market bias
    "setup": "15m",  # liquidity sweep + CHOCH
    "entry": "5m",   # FVG entry
}

# Candle limits per timeframe
CANDLE_LIMITS = {
    "htf": 1000,
    "setup": 1000,
    "entry": 1000,
}

# Scanner settings
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "30"))

# Market structure / liquidity detection
SWING_LOOKBACK = 3
EQUALITY_TOLERANCE = 0.001  # 0.1% tolerance for equal highs/lows
SWEEP_LOOKBACK_BARS = 5
FVG_MAX_AGE_BARS = 60

# Risk management
RISK_PER_TRADE = 0.01  # 1% of account balance
ACCOUNT_BALANCE = 10_000.0
MIN_RISK_REWARD = 2.0
SL_BUFFER = 0.0  # optional buffer added beyond sweep level

# Volatility filter (ATR)
ATR_FILTER_ENABLED = False
ATR_PERIOD = 14
ATR_MIN_PCT = 0.15  # minimum ATR as % of price for acceptable volatility

# Session filter (times in SESSION_TIMEZONE)
SESSION_TIMEZONE = "UTC"
SESSIONS = {
    "london": {"start": "07:00", "end": "16:00"},
    "newyork": {"start": "12:00", "end": "21:00"},
}

# Telegram notifier
TELEGRAM_ENABLED = _env_bool("TELEGRAM_ENABLED", False)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_DEDUP_TTL_SECONDS = int(os.getenv("TELEGRAM_DEDUP_TTL_SECONDS", "3600"))
TELEGRAM_DEDUP_STORAGE_PATH = os.getenv(
    "TELEGRAM_DEDUP_STORAGE_PATH", "logs/telegram_sent.json"
)

# UI (Web)
WEB_UI_HOST = "0.0.0.0"
WEB_UI_PORT = 8501
UI_REFRESH_SECONDS = 30
UI_MAX_BARS = 1000
EXPORT_SIGNALS_CSV = False
SIGNALS_CSV_PATH = "logs/signals.csv"

# Logging / debugging
LOG_LEVEL = "INFO"
DEBUG_EXAMPLE_SIGNAL = False



