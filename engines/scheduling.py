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
from .youtube import VideoStatusCheckError


class SchedulingDriftError(Exception):
    """
    Raised when YouTube positively confirms the local database's idea
    of the most recently scheduled video is wrong — either the video
    no longer exists there at all, or its real publishAt disagrees
    with what we last recorded. Better to stop the run and surface
    this loudly than silently schedule the next video on top of a
    wrong assumption — this is exactly the failure mode that caused
    the original Fact 175-184 numbering collision (§ MASTER_CONTINUATION_PROMPT.md).

    Means: go check YouTube Studio by hand — something really changed
    out-of-band (video removed/flagged, or a manual Studio edit).
    """


class SchedulingStatusCheckError(Exception):
    """
    Raised when compute_next_publish_at() couldn't verify the most
    recently scheduled video's real YouTube status because the status
    check itself failed (auth, quota, transient network/server error)
    — distinct from SchedulingDriftError, which means YouTube
    positively confirmed something is wrong.

    Means: retry, or check credentials/quota — NOT "a video was
    removed."
    """


def _parse_iso(ts: str) -> datetime:
    # YouTube returns Zulu-suffixed timestamps ("...Z"); fromisoformat
    # only accepts that suffix on Python 3.11+, and this codebase
    # targets 3.9-3.12 (Kokoro constraint), so normalize it first.
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _to_iso_z(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


# A public video's real publishedAt can land a few seconds/minutes after its
# scheduled slot. Without this tolerance, "anchor + 24h" would fall a few
# seconds past the next slot and get bumped a whole extra day.
_SLOT_TOLERANCE = timedelta(minutes=30)


def _snap_to_slot(earliest: datetime, slot_utc: str) -> datetime:
    """
    Returns the first daily slot (HH:MM UTC) at or after `earliest`
    (allowing _SLOT_TOLERANCE of slack, see above).
    """
    hour, minute = (int(x) for x in slot_utc.split(":"))
    candidate = earliest.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate < earliest - _SLOT_TOLERANCE:
        candidate += timedelta(days=1)
    return candidate


def _next_from(anchor: datetime, now: datetime, sched_cfg: dict) -> datetime:
    """
    Picks the next publish time.

    With scheduling.slot_utc set (e.g. "23:00" == midnight Lagos), every video
    lands on that daily slot: the first slot that is at least cadence_hours
    after the previous video AND at least min_lead_hours from now. So a late
    run (Gemini outage, retries, manual re-run) snaps back to the normal slot
    instead of shifting the whole schedule to whenever the run happened to end.

    Without slot_utc, falls back to the original behaviour
    (max(anchor, now) + cadence_hours).
    """
    cadence = timedelta(hours=sched_cfg.get("cadence_hours", 24))
    slot_utc = sched_cfg.get("slot_utc")
    if not slot_utc:
        return max(anchor, now) + cadence
    min_lead = timedelta(hours=sched_cfg.get("min_lead_hours", 2))
    earliest = max(anchor + cadence, now + min_lead)
    return _snap_to_slot(earliest, slot_utc)


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
    sched_cfg = config.get("scheduling", {})
    cadence_hours = sched_cfg.get("cadence_hours", 24)
    now = datetime.now(timezone.utc)

    record = numbering.get_latest_video_record()
    if record is None or not record.get("youtube_id"):
        # Nothing to anchor on yet (fresh channel, or the only prior
        # videos were unlisted test runs with no real youtube_id).
        return _to_iso_z(_next_from(now, now, sched_cfg))

    try:
        remote = publisher.get_video_status(record["youtube_id"])
    except VideoStatusCheckError as e:
        raise SchedulingStatusCheckError(
            f"Could not verify fact {record.get('fact_number')}'s "
            f"(youtube_id={record['youtube_id']}) status on YouTube: {e}"
        ) from e

    if remote is None:
        raise SchedulingDriftError(
            f"Fact {record.get('fact_number')} (youtube_id={record['youtube_id']}) "
            "is in the local database but YouTube confirms it no longer exists. "
            "Refusing to schedule blindly off local data alone."
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

    return _to_iso_z(_next_from(anchor, now, sched_cfg))
