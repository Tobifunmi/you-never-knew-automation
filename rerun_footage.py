from pathlib import Path
from engines.script_engine import parse_script
from engines.captions import generate_word_timestamps, generate_ass_captions
from engines.timeline import build_segment_timeline
from engines.footage import download_footage_for_script
from engines.renderer import normalize_all_segments, concatenate_segments, burn_in_captions
from engines.metadata import make_metadata
from engines.youtube import YouTubePublisher
from engines import numbering

FACT_NUMBER = 175
WORK_DIR = Path(f"work/Fact_{FACT_NUMBER}_pangolins")
SCRIPT_PATH = "test_assets/Pangolins.txt"

# Reuse existing narration + word timestamps, no ElevenLabs/Whisper re-run
narration_path = WORK_DIR / "narration.mp3"
if not narration_path.exists():
    raise SystemExit(f"narration.mp3 not found at {narration_path} — can't reuse it.")

raw_text = Path(SCRIPT_PATH).read_text(encoding="utf-8")
script = parse_script(raw_text, fact_number=FACT_NUMBER)

print("Re-transcribing existing narration for word timestamps (Whisper, no ElevenLabs cost)...")
words = generate_word_timestamps(str(narration_path))

print("Rebuilding timeline...")
timeline = build_segment_timeline(script, words)

print("Downloading footage using overrides...")
footage_result = download_footage_for_script(script, str(WORK_DIR / "footage"))
print(f"Footage: {footage_result['success_count']}/{footage_result['total_facts']} downloaded")
if footage_result["failures"]:
    raise SystemExit(f"Footage failures: {footage_result['failures']}")

print("Regenerating captions file...")
ass_path = generate_ass_captions(words, str(WORK_DIR / "captions.ass"))

print("Rendering...")
normalized = normalize_all_segments(timeline, str(WORK_DIR / "footage"), str(WORK_DIR / "normalized"))
combined_path = concatenate_segments(normalized, str(narration_path), str(WORK_DIR / "combined_no_captions.mp4"))
final_path = burn_in_captions(combined_path, ass_path, str(WORK_DIR / "final_output.mp4"))
print(f"Rendered: {final_path}")

# Load config for title template
import json
config = json.loads(Path("config.json").read_text(encoding="utf-8"))

metadata = make_metadata(
    fact_number=FACT_NUMBER,
    topic=script["topic"],
    intro=script["hook"],
    title_template=config["title_template"],
)

print("Uploading to YouTube (unlisted)...")
publisher = YouTubePublisher()
publisher.authenticate(interactive=True)

video_id = publisher.upload_video(
    file_path=final_path,
    title=metadata["title"] + " (retest)",
    description=metadata["description"],
    tags=metadata["tags"],
    category_id=config["youtube"].get("category_id", "27"),
    privacy_status="unlisted",
)
print(f"Uploaded: https://www.youtube.com/watch?v={video_id}")

playlist_id = publisher.find_or_create_playlist(metadata["category"], auto_create=True)
if playlist_id:
    publisher.add_to_playlist(playlist_id, video_id)
    print(f"Added to playlist: {metadata['category']}")

print("Done. NOTE: this did NOT update videos.json/topics.json since Fact 175 is already recorded from the first Pangolins run.")