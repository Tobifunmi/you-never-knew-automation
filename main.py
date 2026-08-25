from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from engines import topic_engine
from engines import numbering
from engines import gemini
from engines import music
from engines import notifications
from engines import analytics
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

    # Tracked throughout so a failure email can say exactly where things
    # broke. fact_number/topic/topic_reserved start unset since a failure
    # can happen before any of them exist (e.g. Gemini itself failing in
    # autonomous mode) — the except block below only releases a topic
    # reservation that actually happened.
    current_stage = "Stage A/B: Ingesting script and reserving topic"
    fact_number = None
    topic = None
    topic_reserved = False

    try:
        # --- Analytics: pull 48h+ performance for any video that's
        # crossed that mark and doesn't have it yet, BEFORE topic
        # selection, so the topic prompt can lean on it. Authenticating
        # the publisher this early (rather than at Stage H, as before)
        # is deliberate — analytics needs the same OAuth session, and
        # reusing one instance avoids a second interactive prompt later.
        # Never fatal: analytics.update_performance_log() swallows its
        # own errors, so a broken/missing yt-analytics scope degrades to
        # "no context this run", not a pipeline failure.
        current_stage = "Stage A0: Updating 48h+ video performance log"
        print(f"== {current_stage} ==")
        publisher = YouTubePublisher()
        publisher.authenticate(interactive=not production)
        analytics.update_performance_log(publisher)
        performance_context = analytics.build_performance_context()

        # --- Stage A/B: topic + fact number + script ingestion ---
        current_stage = "Stage A/B: Ingesting script and reserving topic"
        print(f"== {current_stage} ==")

        if script_path:
            print(f"Manual mode: Loading script from {script_path}")
            raw_text = Path(script_path).read_text(encoding="utf-8")
            script = parse_script(raw_text, fact_number=None)
            topic = script["topic"]

            if topic_engine.is_duplicate(topic):
                raise SystemExit(f"ABORTED: topic '{topic}' is already completed or reserved.")
        else:
            print("Autonomous mode: Requesting unique topic and script from Gemini...")
            topic = gemini.get_unique_topic(performance_context=performance_context)
            script = gemini.generate_script(topic)

        fact_number = numbering.get_next_fact_number()
        script["fact_number"] = fact_number

        # Attach fact numbers (1-5) to facts list for rendering/timeline consistency
        for idx, fact_obj in enumerate(script["facts"], start=1):
            fact_obj["fact_number"] = idx

        topic_engine.reserve_topic(topic)
        topic_reserved = True
        print(f"Fact {fact_number}: {topic} (topic reserved)")

        work_dir = ROOT / "work" / f"Fact_{fact_number}_{slugify(topic)}"
        work_dir.mkdir(parents=True, exist_ok=True)

        # --- Stage C: narration ---
        current_stage = "Stage C: Generating narration (ElevenLabs)"
        print(f"== {current_stage} ==")
        narration = generate_narration(script, str(work_dir / "narration.mp3"))
        print(f"Narration: {narration['duration_seconds']}s, {narration['character_count']} chars")

        # --- Word timestamps + timeline ---
        current_stage = "Transcribing narration for word timestamps (Whisper)"
        print(f"== {current_stage} ==")
        words = generate_word_timestamps(narration["path"])
        save_captions_json(words, str(work_dir / "captions.json"))

        current_stage = "Building segment timeline"
        print(f"== {current_stage} ==")
        timeline = build_segment_timeline(script, words)

        # --- Stage D: footage ---
        current_stage = "Stage D: Downloading footage (Pixabay/Pexels)"
        print(f"== {current_stage} ==")
        footage_result = download_footage_for_script(script, str(work_dir / "footage"))
        print(f"Footage: {footage_result['success_count']}/{footage_result['total_facts']} downloaded")
        if footage_result["failures"]:
            # Was `raise SystemExit(...)` — SystemExit isn't an Exception
            # subclass, so it skipped the except block entirely: no topic
            # release, no failure email. FootageError is already the
            # established error type for this stage everywhere else.
            raise FootageError(f"Footage failures: {footage_result['failures']}")

        # --- Stage E: caption file ---
        current_stage = "Stage E: Generating caption file (ASS)"
        print(f"== {current_stage} ==")
        ass_path = generate_ass_captions(words, str(work_dir / "captions.ass"))

        # --- Stage F: render & background music ---
        current_stage = "Stage F: Rendering"
        print(f"== {current_stage} ==")
        normalized = normalize_all_segments(timeline, str(work_dir / "footage"), str(work_dir / "normalized"))
        combined_path = concatenate_segments(
            normalized, narration["path"], str(work_dir / "combined_no_captions.mp4")
        )

        # Download background music based on topic and duration
        current_stage = "Fetching background music (Jamendo)"
        print(f"== {current_stage} ==")
        music_result = music.fetch_and_download_background_track(
            topic=topic,
            min_duration=narration["duration_seconds"],
            output_path=str(work_dir / "background_music.mp3"),
        )
        print(f"Music: {music_result['track_name']} ({music_result['track_id']})")

        # Mix narration + music
        current_stage = "Mixing background music with narration"
        print(f"== {current_stage} ==")
        mixed_video_path = music.mix_background_music(
            video_path=combined_path,
            music_path=music_result["path"],
            output_path=str(work_dir / "combined_with_music.mp4"),
            narration_duration=narration["duration_seconds"],
        )

        # Burn captions onto the mixed audio/video file
        current_stage = "Burning in captions"
        print(f"== {current_stage} ==")
        final_path = burn_in_captions(mixed_video_path, ass_path, str(work_dir / "final_output.mp4"))
        print(f"Rendered: {final_path}")

        # --- Stage G: metadata ---
        current_stage = "Stage G: Generating metadata"
        print(f"== {current_stage} ==")
        metadata = make_metadata(
            fact_number=fact_number,
            topic=topic,
            intro=script["hook"],  # stopgap until a dedicated intro-writing step exists
            title_template=config["title_template"],
        )
        print(f"Title: {metadata['title']}")
        print(f"Category: {metadata['category']}")

        # --- Stage H: upload ---
        privacy_status = "public" if production else "unlisted"
        current_stage = f"Stage H: Uploading to YouTube (privacy={privacy_status})"
        print(f"== {current_stage} ==")

        # `publisher` was already created and authenticated at the top of
        # this run (Stage A0, for analytics) — reused here rather than
        # opening a second OAuth session.

        video_id = publisher.upload_video(
            file_path=final_path,
            title=metadata["title"],
            description=metadata["description"],
            tags=metadata["tags"],
            category_id=config["youtube"].get("category_id", "27"),
            privacy_status=privacy_status,
        )
        published_at = datetime.now(timezone.utc).isoformat()
        print(f"Uploaded: https://www.youtube.com/watch?v={video_id}")

        # --- Record + complete topic — done IMMEDIATELY after upload,
        # BEFORE playlist logic. This ordering is deliberate and load-
        # bearing: it's the actual fix for the Fact 174 near-data-loss
        # bug (playlist step failed on a real upload, and because the
        # record hadn't been saved yet, the video existed live on
        # YouTube with zero trace of it in the database). A previous
        # version of this file had drifted back to playlist-before-record;
        # this restores the documented, correct order.
        current_stage = "Recording video state + completing topic"
        print(f"== {current_stage} ==")
        numbering.record_video_state(
            fact_number=fact_number,
            topic=topic,
            state="published" if production else "uploaded",
            youtube_id=video_id,
            playlist_id=None,  # filled in below if the playlist step succeeds
            title=metadata["title"],
            category=metadata["category"],
            published_at=published_at,
            narration_duration_seconds=narration["duration_seconds"],
            narration_path=narration["path"],
            related_video_id=None,  # reserved for future Related Video work, not yet automated
            music_track_id=music_result["track_id"],
            music_track_name=music_result["track_name"],
        )
        topic_engine.complete_topic(topic)
        print(f"Recorded Fact {fact_number} and completed topic (video is safe regardless of what happens next).")

        # --- Stage I: playlist — isolated on purpose. A failure here
        # (e.g. the same playlistNotFound eventual-consistency delay that
        # caused Fact 174) is real and worth knowing about, so it still
        # sends a failure email, but it must NEVER release the topic or
        # otherwise touch the already-saved upload record above.
        current_stage = "Stage I: Adding to playlist"
        print(f"== {current_stage} ==")
        try:
            playlist_id = publisher.find_or_create_playlist(
                metadata["category"],
                auto_create=config["youtube"].get("auto_create_playlists", True),
            )
            if playlist_id:
                publisher.add_to_playlist(playlist_id, video_id)
                numbering.record_video_state(
                    fact_number=fact_number,
                    topic=topic,
                    state="playlist_added",
                    youtube_id=video_id,
                    playlist_id=playlist_id,
                    title=metadata["title"],
                    category=metadata["category"],
                    published_at=published_at,
                    narration_duration_seconds=narration["duration_seconds"],
                    narration_path=narration["path"],
                    related_video_id=None,
                    music_track_id=music_result["track_id"],
                    music_track_name=music_result["track_name"],
                )
                print(f"Added to playlist: {metadata['category']}")
        except Exception as playlist_error:
            notifications.send_failure_email(
                stage="Stage I: Adding to playlist (non-fatal — video already uploaded and recorded)",
                error=playlist_error,
                fact_number=fact_number,
                topic=topic,
                production=production,
            )
            print(
                f"WARNING: playlist step failed, but the video is already uploaded and "
                f"recorded in the database, so this is NOT treated as a pipeline failure: {playlist_error}"
            )

        print(f"== DONE: Fact {fact_number} complete ==")
        return video_id

    except Exception as e:
        # Broadened from a specific exception tuple to catch anything,
        # including things like HttpError from the YouTube API that
        # weren't in the original tuple — see the accompanying message
        # for why that gap mattered. Only releases the topic if it was
        # actually reserved (a failure before reserve_topic() has nothing
        # to release).
        notifications.send_failure_email(
            stage=current_stage,
            error=e,
            fact_number=fact_number,
            topic=topic,
            production=production,
        )
        if topic_reserved:
            topic_engine.release_topic(topic)
            print(f"PIPELINE FAILED at fact {fact_number}, topic released for retry: {e}")
        else:
            print(f"PIPELINE FAILED before topic reservation: {e}")
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
