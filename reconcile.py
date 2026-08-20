from engines import numbering, topic_engine

numbering.record_video_state(
    fact_number=174,
    topic="Wombats",
    state="playlist_added",
    youtube_id="sa9gPebAdMo",
    playlist_id="PLUA2Lnfg4FRI",
    title="Fact 174: 5 Facts You Didn't Know About Wombats",
    narration_duration_seconds=85.91,
    related_video_id=None,
)
topic_engine.complete_topic("Wombats")
print("Reconciled Fact 174.")