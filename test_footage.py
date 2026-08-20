from engines.footage import download_footage_for_prompt

result = download_footage_for_prompt(
    "Show a colorful pitcher plant attracting an insect before it slips inside the plant's tube, captioned: 'Nature's Sneaky Trap.'",
    "work/Fact_173_test/footage/fact1.mp4"
)
print(result)