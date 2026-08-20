from pathlib import Path
from faster_whisper import WhisperModel

# "base" is a good balance of speed/accuracy for clear narration audio.
# Options: tiny, base, small, medium, large-v3 (larger = more accurate, slower)
MODEL_SIZE = "base"

_model = None


def _get_model():
    """Lazy-load the model once per process (downloads on first use)."""
    global _model
    if _model is None:
        _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    return _model


def generate_word_timestamps(audio_path: str) -> list:
    """
    Transcribes audio_path and returns a flat list of word-level timestamps:
    [{"word": "Pitcher", "start": 0.12, "end": 0.48}, ...]
    """
    model = _get_model()
    segments, info = model.transcribe(audio_path, word_timestamps=True)

    words = []
    for segment in segments:
        for word in segment.words:
            words.append({
                "word": word.word.strip(),
                "start": round(word.start, 2),
                "end": round(word.end, 2),
            })

    return words


def save_captions_json(words: list, output_path: str) -> str:
    import json
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(words, f, indent=2, ensure_ascii=False)
    return str(output_path)

def _format_ass_time(seconds: float) -> str:
    """ASS time format: H:MM:SS.cc (centiseconds)"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _escape_ass_text(text: str) -> str:
    """Escape characters that have special meaning in ASS dialogue text."""
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def generate_ass_captions(words: list, output_path: str, video_width: int = 1080, video_height: int = 1920) -> str:
    """
    Builds an ASS subtitle file showing one word at a time, styled white
    text with black outline, bottom-centered. Burned into video via ffmpeg's
    'ass' filter in a later render step.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    font_size = int(video_width * 0.095)  # bigger text
    margin_v = int(video_height * 0.5)    # unused when centered, kept for consistency

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,4,0,5,40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = []
    for w in words:
        start = _format_ass_time(w["start"])
        end = _format_ass_time(w["end"])
        text = _escape_ass_text(w["word"])
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(lines))

    return str(output_path)