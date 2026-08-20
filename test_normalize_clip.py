from engines.renderer import normalize_segment_clip

result = normalize_segment_clip(
    "work/Fact_173_test/footage/fact1.mp4",
    duration=8.34,
    output_path="work/Fact_173_test/normalized/fact1_norm.mp4"
)
print("Saved:", result)