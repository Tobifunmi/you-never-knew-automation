from engines.footage import extract_search_query
from engines.script_engine import parse_script

with open("test_assets/Wombat.txt", "r", encoding="utf-8") as f:
    script = parse_script(f.read())

for fact in script["facts"]:
    q = extract_search_query(fact["visual_prompt"])
    print(f"Fact {fact['number']}: '{q}'")