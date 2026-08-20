from engines.footage import extract_search_query, search_footage, _pick_best_video_file
from engines.script_engine import parse_script

with open("test_assets/Wombat.txt", "r", encoding="utf-8") as f:
    script = parse_script(f.read())

for fact in script["facts"]:
    q = extract_search_query(fact["visual_prompt"])
    videos = search_footage(q)
    print(f"Fact {fact['number']}: query='{q}' -> {len(videos)} results")
    for v in videos[:3]:
        best = _pick_best_video_file(v.get("video_files", []))
        print(f"    pexels_id={v.get('id')} url={v.get('url')}")