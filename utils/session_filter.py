from __future__ import annotations

from datetime import datetime, time
from typing import Dict
from zoneinfo import ZoneInfo

import config


def _parse_time(value: str) -> time:
    hour, minute = value.split(":")
    return time(hour=int(hour), minute=int(minute))


def is_in_session(
    now: datetime | None = None,
    timezone: str = config.SESSION_TIMEZONE,
    sessions: Dict[str, Dict[str, str]] = config.SESSIONS,
) -> bool:
    """
    Check if current time is within any configured session.
    Handles sessions that can span midnight.
    """
    tz = ZoneInfo(timezone)
    now = now.astimezone(tz) if now else datetime.now(tz)
    current = now.time()

    for session in sessions.values():
        start = _parse_time(session["start"])
        end = _parse_time(session["end"])

        if start <= end:
            if start <= current <= end:
                return True
        else:
            if current >= start or current <= end:
                return True

    return False
