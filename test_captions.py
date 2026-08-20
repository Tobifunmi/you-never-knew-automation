from engines.captions import generate_word_timestamps, save_captions_json

words = generate_word_timestamps("work/Fact_173_test/narration.mp3")

print(f"Total words transcribed: {len(words)}")
print("First 10 words:")
for w in words[:10]:
    print(f"  {w['start']:.2f}s - {w['end']:.2f}s: {w['word']}")

save_path = save_captions_json(words, "work/Fact_173_test/captions.json")
print(f"Saved to: {save_path}")