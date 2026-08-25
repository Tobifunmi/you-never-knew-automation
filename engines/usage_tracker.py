"""
engines/usage_tracker.py

Minimal local call-counter for services with no queryable "remaining
quota" API (Jamendo, Gemini, YouTube Data API), PLUS an optional
per-video correlation for services that DO have a live quota endpoint
(ElevenLabs, Pexels, Pixabay) — the live check tells you % of quota
used, this tells you how many videos that quota was spent across, so
"212 ElevenLabs calls across 43 videos" is derivable even though
ElevenLabs itself has no concept of "videos".

Read by check_usage.py's check_self_tracked() and the Netlify
usage.js function (via database/usage_log.json committed to the repo).

log_call() never raises. A failure to write a usage counter should never
be allowed to break the actual pipeline stage that called it — tracking
is a nice-to-have, not something worth risking a real video over.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

USAGE_LOG_PATH = Path("database/usage_log.json")


def log_call(service: str, count: int = 1, fact_number: Optional[int] = None) -> None:
    """
    Increments the local call counter for `service` (e.g. "jamendo",
    "gemini", "youtube_upload", "elevenlabs", "pexels", "pixabay").
    Creates database/usage_log.json if it doesn't exist yet.

    fact_number, when given, is recorded in a deduped "videos" list on
    that service's entry, so downstream readers can show both a raw
    call count and a distinct-video count (e.g. "9 calls / 2 videos"
    flags a video that needed retries).
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
                "videos": [],
            }
        log[service].setdefault("videos", [])

        log[service]["count"] = log[service].get("count", 0) + count
        log[service]["last_call"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        if fact_number is not None and fact_number not in log[service]["videos"]:
            log[service]["videos"].append(fact_number)

        USAGE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        USAGE_LOG_PATH.write_text(json.dumps(log, indent=2), encoding="utf-8")
    except Exception as e:
        # Deliberately swallowed — see module docstring.
        print(f"usage_tracker: failed to log call for '{service}': {e}")
