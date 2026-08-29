"""
engines/scheduling.py

Computes the publishAt timestamp for the NEXT video, so it lands
`cadence_hours` after the most recently scheduled one — regardless of
whether that previous video has actually gone live yet. This is what
makes daily cron safe with a backlog: each run only needs to know when
the last video is scheduled to go live, not whether it already has.

Replaces the old flow (upload public/unlisted immediately, then
manually flip to private + a future date in Studio by hand), which is
what caused a video to briefly go live before its intended date and
then, once re-scheduled, keep leaning on that original live timestamp
instead of the new one.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import numbering


class SchedulingDriftError(Exception):
    """
    Raised when the local database's idea of the most recently
    scheduled video disagrees with what YouTube itself reports. Better
    to stop the run and surface this loudly than silently schedule the
    next video on top of a wrong assumption — this is exactly the
    failure mode that caused the original Fact 175-184 numbering
    collision (§ MASTER_CONTINUATION_PROMPT.md).
    """


def _parse_iso(ts: str) -> datetime:
    # YouTube returns Zulu-suffixed timestamps ("...Z"); fromisoformat
    # only accepts that suffix on Python 3.11+, and this codebase
    # targets 3.9-3.12 (Kokoro constraint), so normalize it first.
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _to_iso_z(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def compute_next_publish_at(publisher, config) -> str:
    """
    Returns an ISO 8601 UTC timestamp (Zulu-suffixed) for the NEXT
    video's status.publishAt.

    Cross-checks the local database's highest-fact_number record
    against YouTube's own videos().list() response before trusting it
    — same philosophy as analytics.py's live-publish gating — rather
    than trusting local state alone for anything that gates a real
    publish action.
    """
    cadence_hours = config.get("scheduling", {}).get("cadence_hours", 24)
    now = datetime.now(timezone.utc)

    record = numbering.get_latest_video_record()
    if record is None or not record.get("youtube_id"):
        # Nothing to anchor on yet (fresh channel, or the only prior
        # videos were unlisted test runs with no real youtube_id).
        return _to_iso_z(now + timedelta(hours=cadence_hours))

    remote = publisher.get_video_status(record["youtube_id"])
    if remote is None:
        raise SchedulingDriftError(
            f"Fact {record.get('fact_number')} (youtube_id={record['youtube_id']}) "
            "is in the local database but YouTube has no record of it (or the "
            "status check failed). Refusing to schedule blindly off local data alone."
        )

    real_privacy = remote["status"].get("privacyStatus")
    real_publish_at = remote["status"].get("publishAt")

    if real_privacy == "private" and real_publish_at:
        anchor = _parse_iso(real_publish_at)
    elif real_privacy == "public":
        anchor = _parse_iso(remote["snippet"]["publishedAt"])
    else:
        # unlisted, or private with no publishAt (e.g. manually
        # un-scheduled in Studio) — nothing reliable to anchor on.
        anchor = now

    # If we previously recorded what we scheduled this video for, make
    # sure YouTube still agrees. A mismatch means something changed
    # out-of-band (a manual Studio edit) since our last run.
    local_scheduled = record.get("scheduled_publish_at")
    if local_scheduled and real_publish_at:
        drift_seconds = abs(
            (_parse_iso(local_scheduled) - _parse_iso(real_publish_at)).total_seconds()
        )
        if drift_seconds > 60:
            raise SchedulingDriftError(
                f"Fact {record.get('fact_number')}'s locally recorded "
                f"scheduled_publish_at ({local_scheduled}) doesn't match what "
                f"YouTube actually has scheduled ({real_publish_at}). Something "
                "changed out-of-band (a manual Studio edit?) — resolve the "
                "drift before scheduling the next video."
            )

    next_time = max(anchor, now) + timedelta(hours=cadence_hours)
    return _to_iso_z(next_time)
