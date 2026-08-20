import json
from engines.script_engine import parse_script
from engines.metadata import make_metadata
from engines.youtube import YouTubePublisher
from engines.numbering import record_video_state

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

with open("test_assets/sample_script.txt", "r", encoding="utf-8") as f:
    raw = f.read()

script = parse_script(raw, fact_number=173)

metadata = make_metadata(
    fact_number=script["fact_number"],
    topic=script["topic"],
    intro=script["hook"],
    title_template=config["title_template"],
)

print("Uploading:", metadata["title"])

yt = YouTubePublisher()
yt.authenticate()

video_id = yt.upload_video(
    file_path="work/Fact_173_test/final_output.mp4",
    title=metadata["title"],
    description=metadata["description"],
    tags=metadata["tags"],
    category_id=config["youtube"]["category_id"],
    privacy_status="unlisted",
)

print("Uploaded. YouTube video ID:", video_id)

playlist_id = "PLOOM2rEPGwC0"  # Nature Facts, created in Stage H
yt.add_to_playlist(playlist_id, video_id)
print("Added to playlist:", playlist_id)

record_video_state(
    173, "Carnivorous Pitcher Plants", "uploaded",
    youtube_id=video_id,
    title=metadata["title"],
    playlist_id=playlist_id,
)
print("State recorded.")