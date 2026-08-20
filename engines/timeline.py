def build_segment_timeline(script: dict, words: list) -> list:
    """
    Maps each script segment (hook, fact1..5, ending) to a time range in the
    narration audio, using word-count alignment between the original script
    text and the Whisper-transcribed words. This is an approximation: it
    assumes TTS and Whisper produce roughly the same word count per segment,
    which holds well for clean narration but isn't guaranteed word-perfect.

    Returns a list of segments in order:
    [{"label": "hook", "start": 0.0, "end": 3.2, "footage_key": 1}, ...]
    """
    def word_count(text):
        return len(text.split())

    segment_defs = [("hook", script["hook"], None)]
    for fact in script["facts"]:
        segment_defs.append((f"fact{fact['number']}", fact["narration"], fact["number"]))
    segment_defs.append(("ending", script["ending"], None))

    # hook and ending borrow footage from the nearest fact
    first_fact_num = script["facts"][0]["number"]
    last_fact_num = script["facts"][-1]["number"]

    timeline = []
    word_idx = 0

    for i, (label, text, fact_num) in enumerate(segment_defs):
        n = word_count(text)
        segment_words = words[word_idx: word_idx + n]

        if not segment_words:
            raise ValueError(
                f"Ran out of transcribed words while assigning segment '{label}'. "
                f"Word count mismatch between script and transcription."
            )

        start = segment_words[0]["start"]
        word_idx += n

        footage_key = fact_num
        if label == "hook":
            footage_key = first_fact_num
        elif label == "ending":
            footage_key = last_fact_num

        timeline.append({
            "label": label,
            "start": start,
            "footage_key": footage_key,
        })

    # Set each segment's end = next segment's start (no gaps), last = end of audio
    for i in range(len(timeline) - 1):
        timeline[i]["end"] = timeline[i + 1]["start"]
    timeline[-1]["end"] = words[-1]["end"]

    return timeline