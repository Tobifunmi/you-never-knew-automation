import json
from engines.script_engine import parse_script
from engines.timeline import build_segment_timeline

with open("test_assets/sample_script.txt", "r", encoding="utf-8") as f:
    raw = f.read()
script = parse_script(raw, fact_number=173)

with open("work/Fact_173_test/captions.json", "r", encoding="utf-8") as f:
    words = json.load(f)

timeline = build_segment_timeline(script, words)

for seg in timeline:
    duration = seg["end"] - seg["start"]
    print(f"{seg['label']:8s} start={seg['start']:.2f}s end={seg['end']:.2f}s dur={duration:.2f}s footage=fact{seg['footage_key']}")