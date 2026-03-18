import logging
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)


def send_telegram_message(message: str) -> Optional[dict]:
    if not config.TELEGRAM_ENABLED:
        logger.info("Telegram disabled. Message: %s", message)
        return None

    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.warning("Telegram token/chat_id not configured.")
        return None

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": config.TELEGRAM_CHAT_ID, "text": message}

    try:
        resp = requests.post(url, data=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.warning("Failed to send Telegram message: %s", exc)
        return None
