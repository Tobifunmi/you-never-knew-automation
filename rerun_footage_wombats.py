"""
Re-does footage + render for Fact 174 (Wombats) WITHOUT touching ElevenLabs.

Reuses the existing narration.mp3 from the original run. Re-transcribes it
locally with Whisper (free) to rebuild the timeline, then re-runs footage
download using the CURRENT footage.py (which has the exclude_ids variety
fix that didn't exist yet when Wombats was originally produced).

Does NOT upload or touch videos.json/topics.json — Fact 174 is already
recorded (youtube_id sa9gPebAdMo, state "playlist_added"). This script only
gets you a new final_output.mp4 to review. Uploading/replacing is a
separate manual decision, same as how the Pangolins retest was handled.

NOTE ON A REAL LIMITATION (verify before trusting the output):
download_footage_for_prompt()'s waterfall only enforces topic-relevance
checking through its first two tiers (specific Pixabay, specific Pexels).
Its tier-5 generic fallback ("nature landscape" / "scenery") has NO
relevance check and will succeed silently. Wombats' original bug was that
Pexels/Pixabay have very few genuinely relevant wombat clips in the first
place — so once exclude_ids burns through whatever real variety exists,
later facts (4/5) could quietly fall through to generic nature footage
instead of failing loudly. This script prints each fact's actual source
query + video ID + source URL at the end specifically so you can check
this before deciding to keep the render. If you see "nature landscape" or
"scenery" as the query for any fact, that fact isn't really wombat footage.
"""

from pathlib import Path
from engines.script_engine import parse_script
from engines.captions import generate_word_timestamps, generate_ass_captions
from engines.timeline import build_segment_timeline
from engines.footage import download_footage_for_script
from engines.renderer import normalize_all_segments, concatenate_segments, burn_in_captions

FACT_NUMBER = 174
WORK_DIR = Path(f"work/Fact_{FACT_NUMBER}_wombats")
SCRIPT_PATH = "test_assets/Wombat.txt"  # verify this matches your actual filename

# --- Reuse existing narration, no ElevenLabs cost ---
narration_path = WORK_DIR / "narration.mp3"
if not narration_path.exists():
    raise SystemExit(
        f"narration.mp3 not found at {narration_path} — can't reuse it.\n"
        f"Check that WORK_DIR / SCRIPT_PATH above match your actual Wombats folder/script names."
    )

if not Path(SCRIPT_PATH).exists():
    raise SystemExit(
        f"Script file not found at {SCRIPT_PATH} — update SCRIPT_PATH to match "
        f"your actual test_assets filename for Wombats."
    )

raw_text = Path(SCRIPT_PATH).read_text(encoding="utf-8")
script = parse_script(raw_text, fact_number=FACT_NUMBER)

print("Re-transcribing existing narration for word timestamps (Whisper, local/free, no ElevenLabs cost)...")
words = generate_word_timestamps(str(narration_path))

print("Rebuilding timeline...")
timeline = build_segment_timeline(script, words)

print("Downloading fresh footage (Pixabay -> Pexels waterfall, exclude_ids variety fix active)...")
footage_result = download_footage_for_script(script, str(WORK_DIR / "footage"))
print(f"Footage: {footage_result['success_count']}/{footage_result['total_facts']} downloaded")
if footage_result["failures"]:
    raise SystemExit(f"Footage failures: {footage_result['failures']}")

print("Regenerating captions file...")
ass_path = generate_ass_captions(words, str(WORK_DIR / "captions.ass"))

print("Rendering...")
normalized = normalize_all_segments(timeline, str(WORK_DIR / "footage"), str(WORK_DIR / "normalized"))
combined_path = concatenate_segments(normalized, str(narration_path), str(WORK_DIR / "combined_no_captions.mp4"))
final_path = burn_in_captions(combined_path, ass_path, str(WORK_DIR / "final_output_retest.mp4"))
print(f"\nRendered: {final_path}")

# --- Relevance report: check for repeats or silent generic fallback ---
print("\n--- Footage source report (check for repeats / non-wombat clips) ---")
seen_ids = set()
for result in footage_result["downloaded"]:
    vid = result["source_video_id"]
    flag = ""
    if vid in seen_ids:
        flag = "  <-- REPEATED SOURCE ID (variety fix didn't help here)"
    if result["query"] in ("nature landscape", "scenery"):
        flag += "  <-- GENERIC FALLBACK, LIKELY NOT ACTUAL WOMBAT FOOTAGE"
    seen_ids.add(vid)
    print(
        f"Fact {result['fact_number']}: [{result['source']}] "
        f"query='{result['query']}' id={vid} url={result.get('source_url')}{flag}"
    )

print(
    "\nDone. This did NOT upload or touch videos.json/topics.json. "
    "Review final_output_retest.mp4 and the source report above, then decide "
    "whether to replace the live video (sa9gPebAdMo) manually."
)
