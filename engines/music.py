from __future__ import annotations

import os
import random
import subprocess
from pathlib import Path
import requests


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
) -> str:
    """
    Queries Jamendo API for a background track longer than min_duration, 
    matching topic vibe tags, and downloads it locally.
    """
    client_id = client_id or os.getenv("JAMENDO_CLIENT_ID")
    if not client_id:
        raise MusicError("JAMENDO_CLIENT_ID missing in environment variables.")

    tags = get_vibe_tags(topic)
    url = "https://api.jamendo.com/v3.0/tracks/"
    
    # Request high-popularity tracks that permit audio downloading
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

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        raise MusicError(f"Jamendo API query failed: {e}")

    results = data.get("results", [])
    
    # Filter candidates by required duration (must be >= min_duration)
    valid_tracks = [t for t in results if float(t.get("duration", 0)) >= min_duration]

    if not valid_tracks:
        # Fall back to a broader search without strict tag matching if none found
        params["tags"] = "cinematic"
        try:
            fallback_res = requests.get(url, params=params, timeout=15)
            fallback_data = fallback_res.json()
            valid_tracks = [
                t for t in fallback_data.get("results", [])
                if float(t.get("duration", 0)) >= min_duration
            ]
        except Exception as e:
            raise MusicError(f"Jamendo fallback query failed: {e}")

    if not valid_tracks:
        raise MusicError(f"No valid tracks found on Jamendo longer than {min_duration} seconds.")

    # Select a track randomly from candidate pool to ensure variety
    selected_track = random.choice(valid_tracks)
    download_url = selected_track.get("audiodownload") or selected_track.get("audio")

    if not download_url:
        raise MusicError(f"Selected track {selected_track.get('id')} lacks a valid audio stream URL.")

    # Download track file
    try:
        audio_res = requests.get(download_url, timeout=30)
        audio_res.raise_for_status()
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(audio_res.content)
        
        return str(output_file)
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
    Uses FFmpeg to mix background music into the video stream.
    Lowers music volume (default 12%), applies audio fade-out at the video end,
    and cuts audio cleanly to match narration length.
    """
    fade_start = max(0.0, narration_duration - fade_duration)
    
    # FFmpeg complex filter:
    # 1. Scale background music volume to music_volume (12%)
    # 2. Apply audio fade-out at the end
    # 3. Mix narration (audio stream 0) and music (audio stream 1) together
    filter_complex = (
        f"[1:a]volume={music_volume},afade=t=out:st={fade_start:.2f}:d={fade_duration}[bg];"
        f"[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[a]"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
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