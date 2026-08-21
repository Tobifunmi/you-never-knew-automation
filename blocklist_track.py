"""
blocklist_track.py — manually blocklist a Jamendo track so it's never
selected again, e.g. after finding a YouTube Content ID claim in Studio.

Usage:
    python blocklist_track.py <jamendo_track_id> "<reason>"

Example:
    python blocklist_track.py 1234567 "Content ID claim on Fact 180 (Statue of Liberty) - Epic Cinematic Trailer match"

The ID is just the numeric Jamendo track ID (no "jamendo:" prefix needed —
this script adds that namespacing for you, matching how music.py records
and checks it).

To find the ID for a video whose track WASN'T recorded (anything before
this tracking existed, like Fact 180): check database/videos.json for a
"music_track_id" field first — if it's missing, unfortunately there's no
way to recover which track it was after the fact.
"""

import sys
from engines.music import add_to_blocklist

if len(sys.argv) < 2:
    raise SystemExit(
        "Usage: python blocklist_track.py <jamendo_track_id> [\"<reason>\"]\n"
        "Example: python blocklist_track.py 1234567 \"Content ID claim on Fact 180\""
    )

raw_id = sys.argv[1]
reason = sys.argv[2] if len(sys.argv) > 2 else ""

track_id = raw_id if raw_id.startswith("jamendo:") else f"jamendo:{raw_id}"

add_to_blocklist(track_id, reason)
print(f"Blocklisted {track_id}." + (f" Reason: {reason}" if reason else ""))
print("This track will now be skipped on every future run.")
