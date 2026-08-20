from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self, default: Any) -> Any:
        if not self.path.exists():
            self.save(default)
            return default
        with self.path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, data: Any) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp.replace(self.path)


def next_fact_number(videos_path: str | Path, configured_start: int) -> int:
    data = JsonStore(videos_path).load({"videos": [], "next_fact_number": None})
    if data.get("next_fact_number"):
        return int(data["next_fact_number"])

    numbers = [
        int(v["fact_number"])
        for v in data.get("videos", [])
        if str(v.get("fact_number", "")).isdigit()
    ]

    return max(numbers) + 1 if numbers else configured_start + 1


def record_video(
    videos_path: str | Path,
    topics_path: str | Path,
    video_record: dict,
    topic: str,
) -> None:
    videos_store = JsonStore(videos_path)
    videos = videos_store.load({"videos": [], "next_fact_number": None})

    videos["videos"].append(video_record)
    videos["next_fact_number"] = int(video_record["fact_number"]) + 1
    videos_store.save(videos)

    topics_store = JsonStore(topics_path)
    topics = topics_store.load({"completed": [], "reserved": []})

    if topic not in topics["completed"]:
        topics["completed"].append(topic)

    if topic in topics["reserved"]:
        topics["reserved"].remove(topic)

    topics_store.save(topics)
