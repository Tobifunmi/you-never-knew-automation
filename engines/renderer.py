import subprocess
from pathlib import Path

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
TARGET_FPS = 30


class RenderError(Exception):
    pass


def _run_ffmpeg(args: list):
    result = subprocess.run(
        ["ffmpeg", "-y", *args],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RenderError(f"ffmpeg failed:\n{result.stderr[-2000:]}")
    return result


def normalize_segment_clip(footage_path: str, duration: float, output_path: str):
    """
    Loops or trims footage_path to exactly `duration` seconds, scales/crops
    to TARGET_WIDTH x TARGET_HEIGHT, normalizes framerate, strips audio.
    Produces a clip ready for concatenation with other normalized clips.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    vf = (
        f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_WIDTH}:{TARGET_HEIGHT},"
        f"fps={TARGET_FPS}"
    )

    _run_ffmpeg([
        "-stream_loop", "-1",
        "-i", str(footage_path),
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-an",
        str(output_path),
    ])

    return str(output_path)

def normalize_all_segments(timeline: list, footage_dir: str, output_dir: str) -> list:
    """
    Normalizes every segment in the timeline to its correct duration,
    using the appropriate footage file (segments sharing a footage_key,
    like hook/fact1, reuse the same source clip but each gets its own
    normalized output at its own duration).
    """
    footage_dir = Path(footage_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    normalized = []
    for seg in timeline:
        duration = seg["end"] - seg["start"]
        source = footage_dir / f"fact{seg['footage_key']}.mp4"
        out_path = output_dir / f"{seg['label']}_norm.mp4"

        normalize_segment_clip(str(source), duration, str(out_path))
        normalized.append({
            "label": seg["label"],
            "path": str(out_path),
            "duration": duration,
        })

    return normalized

def concatenate_segments(normalized_clips: list, narration_path: str, output_path: str) -> str:
    """
    Concatenates normalized silent video clips in order, then muxes in the
    full narration audio track over the top. Uses ffmpeg's concat demuxer
    (fast, no re-encoding of already-normalized clips) followed by a mux step.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build a concat list file (required format for ffmpeg's concat demuxer)
    concat_list_path = output_path.parent / "concat_list.txt"
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for clip in normalized_clips:
            # ffmpeg concat format requires forward slashes and escaped paths
            clip_path = Path(clip["path"]).resolve().as_posix()
            f.write(f"file '{clip_path}'\n")

    silent_concat_path = output_path.parent / "concat_silent.mp4"

    # Step 1: concatenate video-only clips (stream copy, fast, no quality loss)
    _run_ffmpeg([
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list_path),
        "-c", "copy",
        str(silent_concat_path),
    ])

    # Step 2: mux narration audio onto the concatenated video
    _run_ffmpeg([
        "-i", str(silent_concat_path),
        "-i", str(narration_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        str(output_path),
    ])

    return str(output_path)

def burn_in_captions(video_path: str, ass_path: str, output_path: str) -> str:
    """
    Burns an ASS subtitle file into the video. Requires re-encoding
    (can't stream-copy when applying a video filter).
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ffmpeg's ass filter needs forward-slash paths and escaped colons on Windows
    ass_filter_path = Path(ass_path).resolve().as_posix().replace(":", "\\:")

    _run_ffmpeg([
        "-i", str(video_path),
        "-vf", f"ass='{ass_filter_path}'",
        "-c:v", "libx264",
        "-c:a", "copy",
        str(output_path),
    ])

    return str(output_path)