from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from engines import topic_engine
from engines import numbering
from engines import gemini
from engines import music
from engines.script_engine import parse_script, ScriptParseError
from engines.elevenlabs import generate_narration, NarrationError
from engines.captions import (
    generate_word_timestamps,
    save_captions_json,
    generate_ass_captions,
)
from engines.timeline import build_segment_timeline
from engines.footage import download_footage_for_script, FootageError
from engines.renderer import (
    normalize_all_segments,
    concatenate_segments,
    burn_in_captions,
    RenderError,
)
from engines.metadata import make_metadata
from engines.youtube import YouTubePublisher


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            "config.json does not exist. Copy config.example.json to config.json first."
        )
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[\s_-]+", "_", text)


def auth():
    publisher = YouTubePublisher()
    publisher.authenticate(interactive=True)
    print("YouTube authentication successful.")
    print("token.json has been created locally.")
    print("Keep token.json private; do not commit it to GitHub.")


def show_next_number():
    print(f"Next Fact number: {numbering.get_next_fact_number()}")


def upload_test(file_path: str):
    """Manual debugging helper — uploads an arbitrary file as an unlisted test."""
    config = load_config()

    publisher = YouTubePublisher()
    publisher.authenticate(interactive=True)

    fact_number = numbering.get_next_fact_number()
    topic = "Test Topic"

    metadata = make_metadata(
        fact_number=fact_number,
        topic=topic,
        intro="This is a private/unlisted test upload for the You Never Knew automation system.",
        title_template=config["title_template"],
    )

    print(f"Uploading Fact {fact_number} (manual test)...")
    video_id = publisher.upload_video(
        file_path=file_path,
        title=metadata["title"],
        description=metadata["description"],
        tags=metadata["tags"],
        category_id=config["youtube"].get("category_id", "27"),
        privacy_status="unlisted",
    )
    print(f"Uploaded: https://www.youtube.com/watch?v={video_id}")


def run_pipeline(script_path: str | None = None, production: bool = False):
    """
    Full pipeline: 
    - Manual mode (script_path provided): parse file -> topic check -> reserve
    - Autonomous mode (script_path None): Gemini topic -> Gemini script -> reserve
    -> narration -> captions -> footage -> render -> metadata -> YouTube upload -> playlist -> record.
    """
    config = load_config()

    # --- Stage A/B: topic + fact number + script ingestion ---
    print("== Stage A/B: Ingesting script and reserving topic ==")

    if script_path:
        print(f"Manual mode: Loading script from {script_path}")
        raw_text = Path(script_path).read_text(encoding="utf-8")
        script = parse_script(raw_text, fact_number=None)
        topic = script["topic"]

        if topic_engine.is_duplicate(topic):
            raise SystemExit(f"ABORTED: topic '{topic}' is already completed or reserved.")
    else:
        print("Autonomous mode: Requesting unique topic and script from Gemini...")
        topic = gemini.get_unique_topic()
        script = gemini.generate_script(topic)

    fact_number = numbering.get_next_fact_number()
    script["fact_number"] = fact_number

    # Attach fact numbers (1-5) to facts list for rendering/timeline consistency
    for idx, fact_obj in enumerate(script["facts"], start=1):
        fact_obj["fact_number"] = idx

    topic_engine.reserve_topic(topic)
    print(f"Fact {fact_number}: {topic} (topic reserved)")

    work_dir = ROOT / "work" / f"Fact_{fact_number}_{slugify(topic)}"
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        # --- Stage C: narration ---
        print("== Stage C: Generating narration (ElevenLabs) ==")
        narration = generate_narration(script, str(work_dir / "narration.mp3"))
        print(f"Narration: {narration['duration_seconds']}s, {narration['character_count']} chars")

        # --- Word timestamps + timeline ---
        print("== Transcribing narration for word timestamps (Whisper) ==")
        words = generate_word_timestamps(narration["path"])
        save_captions_json(words, str(work_dir / "captions.json"))

        print("== Building segment timeline ==")
        timeline = build_segment_timeline(script, words)

        # --- Stage D: footage ---
        print("== Stage D: Downloading footage (Pexels) ==")
        footage_result = download_footage_for_script(script, str(work_dir / "footage"))
        print(f"Footage: {footage_result['success_count']}/{footage_result['total_facts']} downloaded")
        if footage_result["failures"]:
            raise SystemExit(f"ABORTED: footage failures: {footage_result['failures']}")

        # --- Stage E: caption file ---
        print("== Stage E: Generating caption file (ASS) ==")
        ass_path = generate_ass_captions(words, str(work_dir / "captions.ass"))

# --- Stage F: render & background music ---
        print("== Stage F: Rendering ==")
        normalized = normalize_all_segments(timeline, str(work_dir / "footage"), str(work_dir / "normalized"))
        combined_path = concatenate_segments(
            normalized, narration["path"], str(work_dir / "combined_no_captions.mp4")
        )

        # Download background music based on topic and duration
        print("== Fetching background music (Jamendo) ==")
        music_track_path = music.fetch_and_download_background_track(
            topic=topic,
            min_duration=narration["duration_seconds"],
            output_path=str(work_dir / "background_music.mp3"),
        )

        # Mix narration + music
        print("== Mixing background music with narration ==")
        mixed_video_path = music.mix_background_music(
            video_path=combined_path,
            music_path=music_track_path,
            output_path=str(work_dir / "combined_with_music.mp4"),
            narration_duration=narration["duration_seconds"],
        )

        # Burn captions onto the mixed audio/video file
        final_path = burn_in_captions(mixed_video_path, ass_path, str(work_dir / "final_output.mp4"))
        print(f"Rendered: {final_path}")

        # --- Stage G: metadata ---
        print("== Stage G: Generating metadata ==")
        metadata = make_metadata(
            fact_number=fact_number,
            topic=topic,
            intro=script["hook"],  # stopgap until a dedicated intro-writing step exists
            title_template=config["title_template"],
        )
        print(f"Title: {metadata['title']}")
        print(f"Category: {metadata['category']}")

        # --- Stage H/I: playlist + upload ---
        privacy_status = "public" if production else "unlisted"
        print(f"== Stage H/I: Uploading to YouTube (privacy={privacy_status}) ==")

        publisher = YouTubePublisher()
        publisher.authenticate(interactive=True)

        video_id = publisher.upload_video(
            file_path=final_path,
            title=metadata["title"],
            description=metadata["description"],
            tags=metadata["tags"],
            category_id=config["youtube"].get("category_id", "27"),
            privacy_status=privacy_status,
        )
        print(f"Uploaded: https://www.youtube.com/watch?v={video_id}")

        playlist_id = publisher.find_or_create_playlist(
            metadata["category"],
            auto_create=config["youtube"].get("auto_create_playlists", True),
        )
        if playlist_id:
            publisher.add_to_playlist(playlist_id, video_id)
            print(f"Added to playlist: {metadata['category']}")

        # --- Record + complete topic ---
        numbering.record_video_state(
            fact_number=fact_number,
            topic=topic,
            state="published" if production else "uploaded",
            youtube_id=video_id,
            playlist_id=playlist_id,
            title=metadata["title"],
            narration_duration_seconds=narration["duration_seconds"],
            narration_path=narration["path"],
            related_video_id=None,  # reserved for Stage J (Playwright), not yet automated
        )
        topic_engine.complete_topic(topic)

        print(f"== DONE: Fact {fact_number} complete ==")
        return video_id

    except (NarrationError, FootageError, RenderError, ScriptParseError, gemini.GeminiError, music.MusicError) as e:
        # Release the topic reservation so it can be retried later, since the
        # pipeline failed before anything was actually published.
        topic_engine.release_topic(topic)
        print(f"PIPELINE FAILED at fact {fact_number}, topic released for retry: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="You Never Knew automated video factory."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("auth", help="Authorize this machine for YouTube.")
    sub.add_parser("next-number", help="Show the next Fact number.")

    upload = sub.add_parser("upload-test", help="Upload an existing MP4 as an unlisted test.")
    upload.add_argument("file", help="Path to an MP4 file.")

    run = sub.add_parser("run", help="Run the full pipeline from a raw script file or autonomously with Gemini.")
    run.add_argument(
        "script_file", 
        nargs="?", 
        default=None, 
        help="Optional path to a raw script .txt file. If omitted, Gemini generates topic and script automatically."
    )
    run.add_argument(
        "--production",
        action="store_true",
        help="Publish publicly instead of unlisted. DEFAULT IS UNLISTED/TEST.",
    )

    args = parser.parse_args()

    if args.command == "auth":
        auth()
    elif args.command == "next-number":
        show_next_number()
    elif args.command == "upload-test":
        upload_test(args.file)
    elif args.command == "run":
        run_pipeline(script_path=args.script_file, production=args.production)


if __name__ == "__main__":
    main()