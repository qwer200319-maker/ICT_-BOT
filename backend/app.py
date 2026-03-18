from __future__ import annotations

import os
import sys
import time
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request\nfrom flask_sock import Sock
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

app = Flask(__name__)\nsock = Sock(app)

# Allow frontend (Vercel) to call backend (Render)
CORS(app, resources={r"/api/*": {"origins": "*"}})

CACHE_TTL_SECONDS = int(os.getenv("API_CACHE_TTL_SECONDS", "15"))
CACHE: Dict[str, Dict[str, Any]] = {}
REFRESHING: set[str] = set()
REFRESH_LOCK = threading.Lock()


def _cache_key(pair: str, tf: str, include_fvg: bool, include_liq: bool) -> str:
    return f"{pair}:{tf}:fvg{int(include_fvg)}:liq{int(include_liq)}"


def _get_cache(pair: str, tf: str, include_fvg: bool, include_liq: bool) -> Optional[Dict[str, Any]]:
    key = _cache_key(pair, tf, include_fvg, include_liq)
    entry = CACHE.get(key)
    if not entry:
        return None
    if (time.time() - entry["ts"]) > CACHE_TTL_SECONDS:
        return None
    return entry["data"]


def _set_cache(pair: str, tf: str, include_fvg: bool, include_liq: bool, data: Dict[str, Any]) -> None:
    key = _cache_key(pair, tf, include_fvg, include_liq)
    CACHE[key] = {"ts": time.time(), "data": data}


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


def _compute_snapshot(pair: str, tf: str, include_fvg: bool, include_liq: bool) -> Optional[Dict[str, Any]]:
    limit = _limit_for_tf(tf)
    df = fetch_candles(pair, tf, limit)
    if df is None or df.empty:
        return None

    pools = detect_liquidity_pools(df) if include_liq else []
    sweep = detect_liquidity_sweep(df, pools) if include_liq else None
    fvgs = detect_fvgs(df) if include_fvg else []

    payload = {
        "ok": True,
        "pair": pair,
        "tf": tf,
        "session_ok": is_in_session(),
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
    return payload


def _refresh_async(pair: str, tf: str, include_fvg: bool, include_liq: bool) -> None:
    key = _cache_key(pair, tf, include_fvg, include_liq)
    with REFRESH_LOCK:
        if key in REFRESHING:
            return
        REFRESHING.add(key)

    def _worker() -> None:
        try:
            payload = _compute_snapshot(pair, tf, include_fvg, include_liq)
            if payload:
                _set_cache(pair, tf, include_fvg, include_liq, payload)
        finally:
            with REFRESH_LOCK:
                REFRESHING.discard(key)

    threading.Thread(target=_worker, daemon=True).start()


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
    force = request.args.get("force", "0") == "1"
    include_fvg = request.args.get("fvg", "1") != "0"
    include_liq = request.args.get("liq", "1") != "0"
    since = request.args.get("since", "").strip()
    if not pair:
        return jsonify({"ok": False, "error": "pair is required"}), 400

    session_ok = is_in_session()

    if not force:
        key = _cache_key(pair, tf, include_fvg, include_liq)
        entry = CACHE.get(key)
        if entry:
            cached = entry["data"]
            last_ts = cached.get("ohlc", {}).get("time", [""])[-1]
            if (time.time() - entry["ts"]) <= CACHE_TTL_SECONDS:
                if since and since == last_ts:
                    return jsonify({"ok": True, "not_modified": True, "last": last_ts, "session_ok": session_ok})
                payload = dict(cached)
                payload["session_ok"] = session_ok
                return jsonify(payload)
            _refresh_async(pair, tf, include_fvg, include_liq)
            payload = dict(cached)
            payload["session_ok"] = session_ok
            payload["stale"] = True
            return jsonify(payload)

    payload = _compute_snapshot(pair, tf, include_fvg, include_liq)
    if payload is None:
        return jsonify({"ok": False, "error": "data unavailable"}), 503

    _set_cache(pair, tf, include_fvg, include_liq, payload)
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
@sock.route('/ws/<path:stream>')
def ws_proxy(ws, stream: str):
    """
    Simple WebSocket proxy to upstream (e.g., Binance WS).
    """
    upstream_base = os.getenv('WS_UPSTREAM_BASE', 'wss://stream.binance.com:9443/ws')
    target = f"{upstream_base}/{stream}"
    try:
        from websocket import create_connection, WebSocketTimeoutException
        upstream = create_connection(target, timeout=10)
        upstream.settimeout(1)
    except Exception:
        try:
            ws.send('{"ok":false,"error":"upstream_connect_failed"}')
        except Exception:
            pass
        return
    try:
        while True:
            if getattr(ws, 'closed', False):
                break
            try:
                msg = upstream.recv()
                if msg is not None:
                    ws.send(msg)
            except WebSocketTimeoutException:
                continue
            except Exception:
                break
    finally:
        try:
            upstream.close()
        except Exception:
            pass
