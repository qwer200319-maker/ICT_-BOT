from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request
from flask_cors import CORS

# Ensure project root is on sys.path when running directly
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from data.fetch_candles import fetch_candles
from scanner.pair_scanner import scan_pair
from strategy.fvg_detector import detect_fvgs
from strategy.liquidity_detector import detect_liquidity_pools, detect_liquidity_sweep
from utils.session_filter import is_in_session

app = Flask(__name__)

# Allow frontend (Vercel) to call backend (Render)
CORS(app, resources={r"/api/*": {"origins": "*"}})


def _df_to_ohlc(df) -> Dict[str, List[Any]]:
    df = df.tail(config.UI_MAX_BARS).copy()
    times = df["time"].dt.strftime("%Y-%m-%dT%H:%M:%SZ").tolist()
    return {
        "time": times,
        "open": df["open"].tolist(),
        "high": df["high"].tolist(),
        "low": df["low"].tolist(),
        "close": df["close"].tolist(),
    }


def _limit_for_tf(tf: str) -> int:
    for key, val in config.TIMEFRAMES.items():
        if tf == key or tf == val:
            return config.CANDLE_LIMITS[key]
    return max(config.CANDLE_LIMITS.values())


def _serialize_signal(result) -> Optional[Dict[str, Any]]:
    if not result or not result.signal:
        return None
    s = result.signal
    return {
        "pair": s.pair,
        "direction": s.direction,
        "entry": s.entry,
        "stop_loss": s.stop_loss,
        "take_profit": s.take_profit,
        "risk_reward": s.risk_reward,
        "reason": s.reason,
        "timestamp_utc": s.timestamp.isoformat(),
    }


@app.get("/")
def root():
    return jsonify({"ok": True, "service": "ict-backend"})


@app.get("/api/scan_all")
def scan_all():
    session_ok = is_in_session()
    signals: List[Dict[str, Any]] = []

    for pair in config.PAIRS:
        result = scan_pair(pair)
        if not result:
            continue
        if not session_ok:
            result.signal = None
        sig = _serialize_signal(result)
        if sig:
            signals.append(sig)

    return jsonify({"session_ok": session_ok, "signals": signals, "pairs": config.PAIRS})


@app.get("/api/snapshot")
def snapshot():
    pair = request.args.get("pair")
    tf = request.args.get("tf", config.TIMEFRAMES["entry"])
    if not pair:
        return jsonify({"ok": False, "error": "pair is required"}), 400

    limit = _limit_for_tf(tf)
    df = fetch_candles(pair, tf, limit)
    if df is None or df.empty:
        return jsonify({"ok": False, "error": "data unavailable"}), 503

    pools = detect_liquidity_pools(df)
    sweep = detect_liquidity_sweep(df, pools)
    fvgs = detect_fvgs(df)

    session_ok = is_in_session()

    payload = {
        "ok": True,
        "pair": pair,
        "tf": tf,
        "session_ok": session_ok,
        "ohlc": _df_to_ohlc(df),
        "pools": [{"level": p.level, "kind": p.kind} for p in pools],
        "sweep": (
            {"direction": sweep.direction, "level": sweep.level} if sweep else None
        ),
        "fvgs": [
            {"direction": z.direction, "lower": z.lower, "upper": z.upper, "index": z.index}
            for z in fvgs
        ],
        "signal": None,
    }

    return jsonify(payload)


@app.get("/api/signals.csv")
def signals_csv():
    if not config.EXPORT_SIGNALS_CSV:
        return jsonify({"ok": False, "error": "CSV export disabled"}), 403

    session_ok = is_in_session()
    rows = []
    for pair in config.PAIRS:
        result = scan_pair(pair)
        if not result:
            continue
        if not session_ok:
            result.signal = None
        sig = _serialize_signal(result)
        if sig:
            rows.append(sig)

    if not rows:
        return jsonify({"ok": False, "error": "no signals"}), 404

    import pandas as pd

    os.makedirs(os.path.dirname(config.SIGNALS_CSV_PATH), exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(config.SIGNALS_CSV_PATH, index=False)
    return jsonify({"ok": True, "path": config.SIGNALS_CSV_PATH})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8501"))
    app.run(host="0.0.0.0", port=port, debug=False)
