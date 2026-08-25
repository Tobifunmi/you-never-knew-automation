"""
engines/analytics.py

Pulls YouTube Analytics for videos that have cleared 48 hours since
publish, so recent performance can influence the next topic pick.

Runs once at the START of every pipeline run (before topic selection),
scanning the ENTIRE videos.json list — not just the most recently
published video — so anything that crossed the 48h mark but was missed
(a paused run, a manual skip, etc.) still gets picked up. Once a
video's performance has been captured it is not re-queried on later
runs; this is a one-time "how did it land" snapshot taken at the 48h
mark, not a continuously-refreshed number.

Requires the yt-analytics.readonly OAuth scope on top of the existing
upload scope (see engines/youtube.py SCOPES) — if the current
token.json predates this, one fresh interactive re-auth is needed
(`python main.py auth`) to pick up the new scope.

Never raises out of its public functions — a failure here should never
break the actual video pipeline. Same philosophy as usage_tracker.py.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .metadata import guess_category
from . import usage_tracker

VIDEOS_PATH = Path("database/videos.json")

MIN_AGE_FOR_ANALYTICS = timedelta(hours=48)

METRICS = "views,likes,comments,averageViewPercentage,estimatedMinutesWatched"


def _load_videos() -> dict:
    if not VIDEOS_PATH.exists():
        return {"videos": [], "next_fact_number": None}
    return json.loads(VIDEOS_PATH.read_text(encoding="utf-8"))


def _save_videos(data: dict) -> None:
    VIDEOS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _get_analytics_service(publisher):
    """Reuses the same OAuth credentials YouTubePublisher already holds."""
    if publisher.youtube is None or publisher.credentials is None:
        publisher.authenticate(interactive=False)
    return build("youtubeAnalytics", "v2", credentials=publisher.credentials)


def _fetch_video_metrics(analytics_service, video_id: str, start_date: str, end_date: str) -> Optional[dict]:
    try:
        usage_tracker.log_call("youtube_analytics")
        response = analytics_service.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics=METRICS,
            filters=f"video=={video_id}",
        ).execute()
    except HttpError as e:
        print(f"analytics: YouTube Analytics query failed for {video_id}: {e}")
        return None

    rows = response.get("rows")
    if not rows:
        return None

    headers = [h["name"] for h in response.get("columnHeaders", [])]
    values = rows[0]
    return dict(zip(headers, values))


def update_performance_log(publisher) -> list:
    """
    Scans database/videos.json for every video that:
      - has a youtube_id and a published_at timestamp
      - is at least 48 hours old
      - does not yet have a "performance" block

    and fetches its cumulative performance-to-date from the YouTube
    Analytics API, writing it back into that video's record. Returns
    the list of records updated this run (possibly empty).
    """
    try:
        data = _load_videos()
        videos = data.get("videos", [])
        now = datetime.now(timezone.utc)

        eligible = []
        for v in videos:
            if not v.get("youtube_id") or not v.get("published_at"):
                continue
            if v.get("performance"):
                continue
            try:
                published_at = datetime.fromisoformat(v["published_at"])
            except ValueError:
                continue
            if now - published_at < MIN_AGE_FOR_ANALYTICS:
                continue
            eligible.append((v, published_at))

        if not eligible:
            return []

        analytics_service = _get_analytics_service(publisher)

        updated = []
        for v, published_at in eligible:
            start_date = published_at.strftime("%Y-%m-%d")
            end_date = now.strftime("%Y-%m-%d")
            metrics = _fetch_video_metrics(analytics_service, v["youtube_id"], start_date, end_date)
            if metrics is None:
                continue
            v["performance"] = metrics
            v["performance_captured_at"] = now.isoformat()
            updated.append(v)

        if updated:
            _save_videos(data)
            print(f"analytics: captured 48h+ performance for {len(updated)} video(s).")

        return updated

    except Exception as e:
        # Never let analytics collection break the actual video pipeline.
        print(f"analytics: update_performance_log failed, continuing without it: {e}")
        return []


def build_performance_context(min_videos: int = 3) -> str:
    """
    Summarizes performance-by-category from whatever's been captured so
    far, for inclusion in the Gemini topic prompt. Returns "" if there
    isn't enough data yet to say anything meaningful (avoids skewing
    topic choice off one or two data points).
    """
    try:
        data = _load_videos()
        videos = [v for v in data.get("videos", []) if v.get("performance")]
        if len(videos) < min_videos:
            return ""

        by_category = {}
        for v in videos:
            category = guess_category(v.get("topic", ""))
            pct = v["performance"].get("averageViewPercentage")
            if pct is None:
                continue
            by_category.setdefault(category, []).append(float(pct))

        averages = {cat: sum(vals) / len(vals) for cat, vals in by_category.items() if vals}
        if not averages:
            return ""

        ranked = sorted(averages.items(), key=lambda kv: kv[1], reverse=True)
        lines = [f"- {cat}: {avg:.0f}% average view retention" for cat, avg in ranked]

        return (
            "Recent performance by category (average YouTube view retention, "
            "from videos with at least 48 hours of data):\n"
            + "\n".join(lines)
            + "\n\nLean toward categories with higher retention when they fit "
              "the variety requirement above; don't abandon underperforming "
              "categories entirely, just don't over-index on them."
        )
    except Exception as e:
        print(f"analytics: build_performance_context failed, skipping context: {e}")
        return ""
