import json
from pathlib import Path

VIDEOS_PATH = Path("database/videos.json")


def _load():
    if not VIDEOS_PATH.exists():
        return {"videos": [], "next_fact_number": None}
    with open(VIDEOS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data):
    VIDEOS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(VIDEOS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_next_fact_number() -> int:
    """
    Determine the next Fact number.

    Priority:
    1. Highest fact_number among videos with state 'published' or 'uploaded'.
    2. Fall back to the stored next_fact_number seed value.
    3. Fall back to 1 if nothing exists at all (fresh project).
    """
    data = _load()
    videos = data.get("videos", [])

    completed_numbers = [
        v["fact_number"] for v in videos
        if v.get("fact_number") is not None
        # "scheduled" = privately uploaded with a future status.publishAt
        # (see engines/scheduling.py) — the fact number is spoken for
        # even though the video isn't public yet.
        and v.get("state") in ("published", "uploaded", "playlist_added", "scheduled")
    ]

    if completed_numbers:
        return max(completed_numbers) + 1

    seed = data.get("next_fact_number")
    if seed is not None:
        return seed

    return 1


def get_latest_video_record() -> dict | None:
    """
    The video record with the highest fact_number, regardless of state.
    Used by engines/scheduling.py as the starting point for cross-
    checking against YouTube's real status before scheduling the next
    video's publishAt.
    """
    data = _load()
    videos = data.get("videos", [])
    numbered = [v for v in videos if v.get("fact_number") is not None]
    if not numbered:
        return None
    return max(numbered, key=lambda v: v["fact_number"])


def record_video_state(fact_number: int, topic: str, state: str, **extra):
    """
    Create or update a video record by fact_number. Extra kwargs (youtube_id,
    playlist_id, related_video_id, etc.) get merged into the record.
    """
    data = _load()
    videos = data.get("videos", [])

    record = None
    for v in videos:
        if v.get("fact_number") == fact_number:
            record = v
            break

    if record is None:
        record = {"fact_number": fact_number, "topic": topic}
        videos.append(record)

    record["state"] = state
    record.update(extra)

    data["videos"] = videos
    _save(data)
    return record