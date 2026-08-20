import json
from engines.script_engine import parse_script
from engines.metadata import make_metadata

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

print("TITLE:", metadata["title"])
print()
print("CATEGORY:", metadata["category"])
print()
print("DESCRIPTION:")
print(metadata["description"])
print()
print("TAGS:", metadata["tags"])