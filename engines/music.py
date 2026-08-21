from __future__ import annotations

import os
import random
import subprocess
from pathlib import Path
import json
import requests

from . import usage_tracker


class MusicError(Exception):
    """Custom exception raised when background audio retrieval or mixing fails."""
    pass


# Map topic / content archetypes to high-quality background music tags on Jamendo
VIBE_MAP = {
    "history": "ambient+cinematic",
    "space": "space+ambient",
    "science": "electronic+ambient",
    "tech": "corporate+technology",
    "nature": "acoustic+documentary",
    "crime": "dark+suspense",
    "default": "cinematic+ambient",
}

# A track shorter than this sounds choppy/obviously looped even with a
# crossfade-free hard loop, so we never accept anything below this floor.
# A track AT OR ABOVE this floor but shorter than the narration is fine —
# mix_background_music() loops it to fill the remaining length.
MIN_LOOPABLE_DURATION = 15.0

MUSIC_BLOCKLIST_PATH = Path("database/music_blocklist.json")


def _load_blocklist() -> set:
    """
    Returns the set of namespaced track IDs (e.g. "jamendo:123456") that
    have caused real problems before (e.g. a YouTube Content ID claim) and
    must never be selected again. Missing/unreadable file just means an
    empty blocklist — this should never crash a pipeline run.
    """
    if not MUSIC_BLOCKLIST_PATH.exists():
        return set()
    try:
        data = json.loads(MUSIC_BLOCKLIST_PATH.read_text(encoding="utf-8"))
        return set(data.get("blocked_track_ids", []))
    except Exception as e:
        print(f"music: failed to read blocklist ({e}), proceeding with an empty one.")
        return set()


def add_to_blocklist(track_id: str, reason: str = "") -> None:
    """
    Adds a track ID (namespaced, e.g. "jamendo:123456") to the persistent
    blocklist so it's never selected again. Safe to call multiple times
    with the same ID. Used by blocklist_track.py for manual additions
    (e.g. after discovering a YouTube Content ID claim) and available for
    the pipeline itself to call if a claim is ever detected automatically
    in the future.
    """
    MUSIC_BLOCKLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    if MUSIC_BLOCKLIST_PATH.exists():
        try:
            data = json.loads(MUSIC_BLOCKLIST_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {"blocked_track_ids": [], "reasons": {}}
    else:
        data = {"blocked_track_ids": [], "reasons": {}}

    if track_id not in data["blocked_track_ids"]:
        data["blocked_track_ids"].append(track_id)
    if reason:
        data.setdefault("reasons", {})[track_id] = reason

    MUSIC_BLOCKLIST_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_vibe_tags(topic: str) -> str:
    """Select appropriate music tags based on topic keywords."""
    topic_lower = topic.lower()
    for key, tags in VIBE_MAP.items():
        if key in topic_lower:
            return tags
    return VIBE_MAP["default"]


def fetch_and_download_background_track(
    topic: str,
    min_duration: float,
    output_path: str,
    client_id: str | None = None,
) -> dict:
    """
    Queries Jamendo API for a background track matching topic vibe tags and
    downloads it locally.

    Preference order:
      1. A track >= min_duration (full narration length) — no looping needed.
      2. If none exists, the LONGEST available track >= MIN_LOOPABLE_DURATION,
         which mix_background_music() will loop to fill the narration length.
      3. Same two tiers again on a broader "cinematic" tag fallback if the
         topic-specific tags returned nothing usable.

    Only raises MusicError if nothing at or above MIN_LOOPABLE_DURATION turns
    up in either tag search — i.e. genuinely no usable track exists, not just
    "nothing long enough to avoid looping."
    """
    client_id = client_id or os.getenv("JAMENDO_CLIENT_ID")
    if not client_id:
        raise MusicError("JAMENDO_CLIENT_ID missing in environment variables.")

    tags = get_vibe_tags(topic)
    url = "https://api.jamendo.com/v3.0/tracks/"

    params = {
        "client_id": client_id,
        "format": "json",
        "tags": tags,
        "speed": "medium",
        "audiodownload_allowed": "true",
        "audioformat": "mp32",  # Good quality VBR MP3
        "order": "popularity_total",
        "limit": 20,
    }

    def _query(query_params: dict) -> list:
        usage_tracker.log_call("jamendo")
        try:
            response = requests.get(url, params=query_params, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            raise MusicError(f"Jamendo API query failed: {e}")

        # Jamendo wraps every response in its own "headers" object reporting
        # whether the call actually succeeded — a 200 HTTP status doesn't
        # mean the query itself worked (quota exhausted, bad params, etc.
        # all come back as HTTP 200 with an empty "results" list otherwise
        # indistinguishable from "genuinely no matching tracks"). Surface
        # this explicitly instead of silently falling through to a generic
        # "no track found" error that hides the real cause.
        api_status = data.get("headers", {})
        if api_status.get("status") == "failed":
            raise MusicError(
                f"Jamendo API reported failure (code {api_status.get('code')}): "
                f"{api_status.get('error_message', 'no error message provided')}"
            )

        return data.get("results", [])

    def _select(results: list) -> dict | None:
        blocklist = _load_blocklist()
        before_count = len(results)
        results = [t for t in results if f"jamendo:{t.get('id')}" not in blocklist]
        removed = before_count - len(results)
        if removed:
            print(f"music: blocklist removed {removed} candidate track(s) from consideration.")

        # Tier 1: full-length, no loop needed.
        full_length = [t for t in results if float(t.get("duration", 0)) >= min_duration]
        if full_length:
            return random.choice(full_length)

        # Tier 2: shorter but loopable — take the longest for the fewest loop seams.
        loopable = [t for t in results if float(t.get("duration", 0)) >= MIN_LOOPABLE_DURATION]
        if loopable:
            return max(loopable, key=lambda t: float(t.get("duration", 0)))

        return None

    results = _query(params)
    selected_track = _select(results)

    if not selected_track:
        # Broader fallback tag search
        fallback_params = dict(params, tags="cinematic")
        fallback_results = _query(fallback_params)
        selected_track = _select(fallback_results)

    if not selected_track:
        raise MusicError(
            f"No Jamendo track >= {MIN_LOOPABLE_DURATION}s found for tags "
            f"'{tags}' or fallback 'cinematic' — nothing usable even with looping."
        )

    download_url = selected_track.get("audiodownload") or selected_track.get("audio")
    if not download_url:
        raise MusicError(f"Selected track {selected_track.get('id')} lacks a valid audio stream URL.")

    try:
        audio_res = requests.get(download_url, timeout=30)
        audio_res.raise_for_status()

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(audio_res.content)

        return {
            "path": str(output_file),
            "track_id": f"jamendo:{selected_track.get('id')}",
            "track_name": selected_track.get("name"),
            "track_url": selected_track.get("shareurl"),
        }
    except Exception as e:
        raise MusicError(f"Failed to download background music file: {e}")


def mix_background_music(
    video_path: str,
    music_path: str,
    output_path: str,
    narration_duration: float,
    music_volume: float = 0.12,
    fade_duration: float = 2.0,
) -> str:
    """
    Uses FFmpeg to mix background music into the video stream. The music
    input is looped indefinitely (-stream_loop -1) so a track shorter than
    the narration still fills the whole video; -shortest / duration=first
    in the mix then cuts everything cleanly to narration length, and the
    fade-out is timed off narration_duration so it always lands correctly
    regardless of how many loop iterations happened.
    """
    fade_start = max(0.0, narration_duration - fade_duration)

    filter_complex = (
        f"[1:a]volume={music_volume},afade=t=out:st={fade_start:.2f}:d={fade_duration}[bg];"
        f"[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[a]"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-stream_loop", "-1",
        "-i", music_path,
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[a]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_path,
    ]

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            raise MusicError(f"FFmpeg audio mixing failed: {res.stderr}")
        return output_path
    except Exception as e:
        raise MusicError(f"Error executing FFmpeg audio mix: {e}")
