from engines.renderer import concatenate_segments

normalized_clips = [
    {"label": "hook", "path": "work/Fact_173_test/normalized/hook_norm.mp4"},
    {"label": "fact1", "path": "work/Fact_173_test/normalized/fact1_norm.mp4"},
    {"label": "fact2", "path": "work/Fact_173_test/normalized/fact2_norm.mp4"},
    {"label": "fact3", "path": "work/Fact_173_test/normalized/fact3_norm.mp4"},
    {"label": "fact4", "path": "work/Fact_173_test/normalized/fact4_norm.mp4"},
    {"label": "fact5", "path": "work/Fact_173_test/normalized/fact5_norm.mp4"},
    {"label": "ending", "path": "work/Fact_173_test/normalized/ending_norm.mp4"},
]

result = concatenate_segments(
    normalized_clips,
    narration_path="work/Fact_173_test/narration.mp3",
    output_path="work/Fact_173_test/combined_no_captions.mp4"
)
print("Saved:", result)