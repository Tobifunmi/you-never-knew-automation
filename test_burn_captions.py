import json
from engines.captions import generate_ass_captions
from engines.renderer import burn_in_captions

with open("work/Fact_173_test/captions.json", "r", encoding="utf-8") as f:
    words = json.load(f)

ass_path = generate_ass_captions(words, "work/Fact_173_test/captions.ass")
print("ASS file saved:", ass_path)

final_path = burn_in_captions(
    "work/Fact_173_test/combined_no_captions.mp4",
    ass_path,
    "work/Fact_173_test/final_output.mp4"
)
print("Final video saved:", final_path)