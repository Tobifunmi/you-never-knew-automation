from pathlib import Path
from dotenv import load_dotenv
from engines import music

# Load variables from .env file into os.environ
load_dotenv()

# Point to your existing work directory from the previous run
work_dir = Path("work").glob("Fact_*")
latest_dir = sorted(work_dir, key=lambda p: p.stat().st_mtime)[-1]

print(f"Testing music integration on: {latest_dir.name}")

# Pick an arbitrary duration for testing (e.g. 30 seconds)
narration_duration = 30.0  

# 1. Fetch background track
print("Fetching track from Jamendo...")
music_track = music.fetch_and_download_background_track(
    topic="space",
    min_duration=narration_duration,
    output_path=str(latest_dir / "test_background_music.mp3"),
)
print(f"Downloaded track to: {music_track}")

# 2. Test mixing with the un-captioned combined MP4
video_input = str(latest_dir / "combined_no_captions.mp4")
output_video = str(latest_dir / "test_combined_with_music.mp4")

if Path(video_input).exists():
    print("Mixing audio with video...")
    music.mix_background_music(
        video_path=video_input,
        music_path=music_track,
        output_path=output_video,
        narration_duration=narration_duration,
    )
    print(f"Success! Test video created at: {output_video}")
else:
    print(f"Could not find {video_input} to test mixing.")