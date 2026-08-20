import json
from engines.script_engine import parse_script
from engines.timeline import build_segment_timeline
from engines.renderer import normalize_all_segments

with open("test_assets/sample_script.txt", "r", encoding="utf-8") as f:
    raw = f.read()
script = parse_script(raw, fact_number=173)

with open("work/Fact_173_test/captions.json", "r", encoding="utf-8") as f:
    words = json.load(f)

timeline = build_segment_timeline(script, words)
normalized = normalize_all_segments(timeline, "work/Fact_173_test/footage", "work/Fact_173_test/normalized")

for n in normalized:
    print(f"{n['label']:8s} {n['duration']:.2f}s -> {n['path']}")