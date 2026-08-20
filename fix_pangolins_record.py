"""
Patches database/videos.json so Fact 175 (Pangolins) points at the retest
video you approved, instead of the original bad-footage upload.

You've already deleted the other (rejected) upload from YouTube directly,
so this only needs to fix the database record — no YouTube API calls here.

Usage:
    python fix_pangolins_record.py
"""

import json
from pathlib import Path

VIDEOS_JSON_PATH = Path("database/videos.json")
FACT_NUMBER = 175
NEW_YOUTUBE_ID = "wF3mXOU5OOA"
OLD_YOUTUBE_ID = "f9E0xQrZrwE"  # the original bad-footage upload, for the sanity check below

data = json.loads(VIDEOS_JSON_PATH.read_text(encoding="utf-8"))
videos = data.get("videos", [])

match = None
for video in videos:
    if video.get("fact_number") == FACT_NUMBER:
        match = video
        break

if not match:
    raise SystemExit(f"No record found for fact_number {FACT_NUMBER} in {VIDEOS_JSON_PATH}.")

current_id = match.get("youtube_id")
if current_id != OLD_YOUTUBE_ID:
    print(
        f"Heads up: expected the current youtube_id to be '{OLD_YOUTUBE_ID}' "
        f"(the known bad-footage video) but found '{current_id}' instead. "
        f"Proceeding anyway, but double-check this is the record you meant to fix."
    )

print(f"Fact {FACT_NUMBER} record before: {json.dumps(match, indent=2)}")

match["youtube_id"] = NEW_YOUTUBE_ID

print(f"\nFact {FACT_NUMBER} record after:  {json.dumps(match, indent=2)}")

VIDEOS_JSON_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
print(f"\nWritten back to {VIDEOS_JSON_PATH}. Commit and push this change.")
