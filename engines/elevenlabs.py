import os
import json
import subprocess
import requests
from pathlib import Path
from dotenv import load_dotenv

from . import usage_tracker

load_dotenv()

API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
MODEL_ID = "eleven_multilingual_v2"  # good default for narration quality
MAX_CHARS = 5000


class NarrationError(Exception):
    pass


def build_narration_text(script: dict) -> str:
    """Concatenate hook + fact narrations + ending into one narration script."""
    parts = [script["hook"]]
    for fact in script["facts"]:
        parts.append(fact["narration"])
    parts.append(script["ending"])
    return " ".join(parts)


def generate_narration(script: dict, output_path: str) -> dict:
    """
    Calls ElevenLabs TTS for the full script narration, saves MP3 to output_path,
    and returns duration info via ffprobe.
    """
    if not API_KEY or not VOICE_ID:
        raise NarrationError("Missing ELEVENLABS_API_KEY or ELEVENLABS_VOICE_ID in .env")

    text = build_narration_text(script)

    if len(text) > MAX_CHARS:
        raise NarrationError(
            f"Narration text is {len(text)} characters, exceeds the {MAX_CHARS} limit "
            f"for a single TTS request. Split into multiple calls (not yet implemented)."
        )

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "xi-api-key": API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": MODEL_ID,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=120)

    # Logged regardless of outcome below (a failed call still spends the
    # request against ElevenLabs' side); fact_number ties this call to the
    # video it was for so the dashboard can show calls-per-video.
    usage_tracker.log_call("elevenlabs", fact_number=script.get("fact_number"))

    if response.status_code != 200:
        raise NarrationError(
            f"ElevenLabs API error {response.status_code}: {response.text[:500]}"
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(response.content)

    duration = _get_duration_seconds(output_path)

    return {
        "path": str(output_path),
        "duration_seconds": duration,
        "character_count": len(text),
    }


def _get_duration_seconds(mp3_path: Path) -> float:
    """Use ffprobe to get exact audio duration."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(mp3_path),
        ],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    return round(float(data["format"]["duration"]), 2)