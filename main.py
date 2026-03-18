import logging
import time

import config
from notifier.telegram_bot import send_telegram_message
from scanner.pair_scanner import scan_pair
from utils.session_filter import is_in_session
from utils.dedup_store import SignalDeduper


def _format_signal(signal) -> str:
    return (
        f"ICT Signal\n"
        f"Pair: {signal.pair}\n"
        f"Direction: {signal.direction}\n"
        f"Entry: {signal.entry:.6f}\n"
        f"Stop Loss: {signal.stop_loss:.6f}\n"
        f"Take Profit: {signal.take_profit:.6f}\n"
        f"Risk-Reward: {signal.risk_reward:.2f}\n"
        f"Reason: {signal.reason}\n"
        f"Time (UTC): {signal.timestamp.isoformat()}"
    )


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    logging.info("ICT bot started.")
    deduper = SignalDeduper(
        config.TELEGRAM_DEDUP_STORAGE_PATH, config.TELEGRAM_DEDUP_TTL_SECONDS
    )
    logging.info("UI: run `python ui/web_ui.py` in a separate terminal.")

    # Example signal generation (optional)
    if config.DEBUG_EXAMPLE_SIGNAL:
        from strategy.entry_model import TradeSignal

        sample = TradeSignal(
            pair="EXAMPLE",
            direction="LONG",
            entry=100.0,
            stop_loss=98.0,
            take_profit=104.0,
            risk_reward=2.0,
            reason="Liquidity Sweep + CHOCH + FVG",
            timestamp=None,
        )
        from datetime import datetime, timezone

        sample.timestamp = datetime.now(timezone.utc)
        send_telegram_message(_format_signal(sample))

    while True:
        if not is_in_session():
            logging.info("Outside trading sessions. Sleeping.")
            time.sleep(config.SCAN_INTERVAL_SECONDS)
            continue

        for pair in config.PAIRS:
            result = scan_pair(pair)
            if result and result.signal:
                signal = result.signal
                if not deduper.is_duplicate(signal):
                    message = _format_signal(signal)
                    logging.info("Signal found: %s %s", pair, signal.direction)
                    send_telegram_message(message)
                    deduper.mark_sent(signal)
                else:
                    logging.info("Duplicate signal skipped: %s %s", pair, signal.direction)

        deduper.cleanup()
        time.sleep(config.SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
