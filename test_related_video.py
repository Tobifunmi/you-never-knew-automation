"""
Standalone supervised test for the related-video End Screen automation.
Run with:

    python test_related_video.py <new_video_id> <current_fact_number>

Example:

    python test_related_video.py dQw4w9WgXcQ 179

This looks up the previous fact's youtube_id from database/videos.json,
then runs the HEADED (visible browser) End Screen automation so you can
watch it and report back exactly where it succeeds or fails.
"""

import sys
from engines.related_video import get_previous_fact_video_id, set_related_video_headed

if len(sys.argv) != 3:
    raise SystemExit(
        "Usage: python test_related_video.py <new_video_id> <current_fact_number>"
    )

new_video_id = sys.argv[1]
current_fact_number = int(sys.argv[2])

prev_id = get_previous_fact_video_id("database/videos.json", current_fact_number)
if not prev_id:
    raise SystemExit(
        f"No youtube_id found for fact {current_fact_number - 1} in database/videos.json. "
        f"Check the fact number you passed, or that the previous record actually has a youtube_id."
    )

print(f"New video:      {new_video_id}")
print(f"Previous video:  {prev_id} (fact {current_fact_number - 1})")
print("Opening a visible browser now — watch it and note which step, if any, fails...\n")

set_related_video_headed(
    video_id=new_video_id,
    related_video_id=prev_id,
    storage_state_path="storage_state.json",
)

print("\nFinished without raising an error. Go check the video's End Screen in Studio to confirm it actually saved correctly.")
