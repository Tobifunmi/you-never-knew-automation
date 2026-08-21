"""
engines/usage_tracker.py

Minimal local call-counter for services with no queryable "remaining
quota" API (Jamendo, Gemini, YouTube Data API). This is NOT a real quota
number — it's just "how many times this pipeline actually called this
service", which is the closest approximation available without adding a
separate Cloud Monitoring credential just for a dashboard.

Read by check_usage.py's check_self_tracked().

log_call() never raises. A failure to write a usage counter should never
be allowed to break the actual pipeline stage that called it — tracking
is a nice-to-have, not something worth risking a real video over.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

USAGE_LOG_PATH = Path("database/usage_log.json")


def log_call(service: str, count: int = 1) -> None:
    """
    Increments the local call counter for `service` (e.g. "jamendo",
    "gemini", "youtube"). Creates database/usage_log.json if it doesn't
    exist yet.
    """
    try:
        if USAGE_LOG_PATH.exists():
            log = json.loads(USAGE_LOG_PATH.read_text(encoding="utf-8"))
        else:
            log = {}

        if service not in log:
            log[service] = {
                "count": 0,
                "since": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }

        log[service]["count"] = log[service].get("count", 0) + count
        log[service]["last_call"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        USAGE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        USAGE_LOG_PATH.write_text(json.dumps(log, indent=2), encoding="utf-8")
    except Exception as e:
        # Deliberately swallowed — see module docstring.
        print(f"usage_tracker: failed to log call for '{service}': {e}")
