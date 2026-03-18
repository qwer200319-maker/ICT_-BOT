from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Dict

import config


@dataclass
class DedupState:
    sent: Dict[str, float]


class SignalDeduper:
    def __init__(self, path: str, ttl_seconds: int) -> None:
        self.path = path
        self.ttl_seconds = ttl_seconds
        self.state = DedupState(sent={})
        self._load()

    def _load(self) -> None:
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "sent" in data:
                self.state.sent = {k: float(v) for k, v in data["sent"].items()}
        except Exception:
            # If corrupted, start fresh
            self.state.sent = {}

    def _save(self) -> None:
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        payload = {"sent": self.state.sent}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(payload, f)

    def _make_key(self, signal) -> str:
        return (
            f"{signal.pair}|{signal.direction}|"
            f"{signal.entry:.6f}|{signal.stop_loss:.6f}|{signal.take_profit:.6f}"
        )

    def is_duplicate(self, signal) -> bool:
        key = self._make_key(signal)
        ts = self.state.sent.get(key)
        if not ts:
            return False
        return (time.time() - ts) < self.ttl_seconds

    def mark_sent(self, signal) -> None:
        key = self._make_key(signal)
        self.state.sent[key] = time.time()
        self._save()

    def cleanup(self) -> None:
        now = time.time()
        self.state.sent = {
            k: v for k, v in self.state.sent.items() if now - v < self.ttl_seconds
        }
        self._save()
