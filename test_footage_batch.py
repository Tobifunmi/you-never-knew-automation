from engines.script_engine import parse_script
from engines.footage import download_footage_for_script

with open("test_assets/sample_script.txt", "r", encoding="utf-8") as f:
    raw = f.read()

script = parse_script(raw, fact_number=173)

result = download_footage_for_script(script, "work/Fact_173_test/footage")

print(f"Success: {result['success_count']}/{result['total_facts']}")
for d in result["downloaded"]:
    print(f"  Fact {d['fact_number']}: query='{d['query']}' -> {d['path']} ({d['width']}x{d['height']})")

if result["failures"]:
    print("Failures:")
    for f in result["failures"]:
        print(f"  Fact {f['fact_number']}: {f['error']}")