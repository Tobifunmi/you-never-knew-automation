from engines import numbering, topic_engine

YOUTUBE_ID = "Ra--YYiOTog"

numbering.record_video_state(
    fact_number=212,
    topic="Dry Ice",
    state="scheduled",
    youtube_id=YOUTUBE_ID,
    playlist_id=None,
    title="Fact 212: 5 Facts You Didn't Know About Dry Ice",
    scheduled_publish_at="2026-10-01T23:00:00Z",  # Oct 2, 12:00 AM Lagos
    related_video_id=None,
)
topic_engine.complete_topic("Dry Ice")
print("Reconciled Fact 212 (Dry Ice).")