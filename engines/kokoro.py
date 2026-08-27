"""
engines/kokoro.py

Narration via Kokoro-82M (github.com/hexgrad/kokoro) — an 82M-parameter,
Apache-2.0-licensed, fully local/offline TTS model. Runs entirely on
CPU, no API key, no character limit, no usage tracking needed here
(nothing external is being called, so there's no quota to log).

Swapped in for engines/elevenlabs.py: ElevenLabs' free tier caps out
around 6 videos/month (10,000 chars/mo ÷ ~1,700 chars/video), which was
already tight at 2x/week and a hard blocker for daily posting. Kokoro
has no such cap, and its Apache-2.0 license is commercial-use-safe from
day one (ElevenLabs' free tier explicitly is not) — closes a licensing
gap that was already flagged as a future blocker, not just a cost one.

Interface (generate_narration signature + return shape, NarrationError)
is kept identical to the ElevenLabs module on purpose, so nothing
downstream needed to change beyond main.py's narration file extension
(.mp3 -> .wav — Kokoro outputs WAV natively via soundfile; there's no
reason to add an unnecessary transcode step just to keep the old
extension).

SETUP REQUIRED (one-time, not automatic):
  - The `espeak-ng` SYSTEM package (not pip-installable) must be
    present. Windows: download the .msi from
    https://github.com/espeak-ng/espeak-ng/releases and run it.
    Linux/CI: `apt-get install espeak-ng` (already added to
    .github/workflows/daily-video.yml alongside ffmpeg).
  - First run downloads ~327MB of model weights from Hugging Face
    (cached afterward at ~/.cache/huggingface — CI caches this
    directory across runs; see the workflow file). This means the
    FIRST local run needs a working internet connection and will be
    noticeably slower than every run after it.
"""

import os
from pathlib import Path

import numpy as np
import soundfile as sf
from dotenv import load_dotenv

load_dotenv()

# Voice pick: "am_adam" is Kokoro's American-English male voice closest
# in register to the ElevenLabs "Adam" voice this replaces — chosen by
# ear, not a technical requirement. Override via KOKORO_VOICE_ID env var
# if you want to audition others (full list: see Kokoro-82M model card
# on Hugging Face, or the SAMPLES.md linked from its GitHub README).
VOICE_ID = os.getenv("KOKORO_VOICE_ID", "am_adam")
LANG_CODE = "a"  # American English — must match the voice's language
SPEED = float(os.getenv("KOKORO_SPEED", "1.0"))
SAMPLE_RATE = 24000  # Kokoro's native output rate, fixed by the model

# Short silence between hook/fact/ending chunks so the concatenated
# audio doesn't sound abruptly stitched together. ~250ms is a natural
# breath-pause length; tune via KOKORO_PAUSE_SECONDS if it sounds off.
PAUSE_SECONDS = float(os.getenv("KOKORO_PAUSE_SECONDS", "0.25"))

_pipeline = None  # lazy-loaded: importing kokoro/loading the model is slow


class NarrationError(Exception):
    pass


def build_narration_text(script: dict) -> str:
    """
    Concatenate hook + fact narrations + ending into one narration
    script. Joined with double-newlines (not spaces, as the ElevenLabs
    version did) — Kokoro's pipeline splits on '\\n+' by default, so
    this chunks generation naturally at hook/fact/ending boundaries
    rather than sending one long unbroken block through the model.
    Newlines aren't spoken; this only affects internal chunking.
    """
    parts = [script["hook"]]
    for fact in script["facts"]:
        parts.append(fact["narration"])
    parts.append(script["ending"])
    return "\n\n".join(parts)


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        from kokoro import KPipeline  # deferred: this import alone is cheap, but
        _pipeline = KPipeline(lang_code=LANG_CODE)  # this line loads model weights
    return _pipeline


def generate_narration(script: dict, output_path: str) -> dict:
    """
    Runs Kokoro locally for the full script narration, saves WAV to
    output_path. No character limit, no API key — nothing external is
    called once the model weights are cached locally.
    """
    text = build_narration_text(script)

    try:
        pipeline = _get_pipeline()
        generator = pipeline(text, voice=VOICE_ID, speed=SPEED)

        chunks = []
        pause = np.zeros(int(PAUSE_SECONDS * SAMPLE_RATE), dtype=np.float32)
        for result in generator:
            if result.audio is None:
                continue  # an empty/whitespace-only split segment; skip it
            audio_np = result.audio.numpy().astype(np.float32)
            if chunks:
                chunks.append(pause)
            chunks.append(audio_np)
    except NarrationError:
        raise
    except Exception as e:
        raise NarrationError(f"Kokoro generation failed: {e}") from e

    if not chunks:
        raise NarrationError("Kokoro produced no audio output for this script.")

    full_audio = np.concatenate(chunks)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), full_audio, SAMPLE_RATE)

    duration = round(len(full_audio) / SAMPLE_RATE, 2)

    return {
        "path": str(output_path),
        "duration_seconds": duration,
        "character_count": len(text),
    }
