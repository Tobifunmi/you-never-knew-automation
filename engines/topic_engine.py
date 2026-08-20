import json
import re
from pathlib import Path

TOPICS_PATH = Path("database/topics.json")


class DuplicateTopicError(Exception):
    pass


def _load():
    if not TOPICS_PATH.exists():
        return {"completed": [], "reserved": []}
    with open(TOPICS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data):
    TOPICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TOPICS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def normalize_topic(topic: str) -> str:
    """Lowercase, strip leading articles, strip trailing 'facts', collapse whitespace."""
    t = topic.strip().lower()
    t = re.sub(r"^(the|a|an)\s+", "", t)
    t = re.sub(r"\s+facts?$", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def get_all_used_topics() -> list:
    """Return the combined completed + reserved topic list (source of truth for exclusions)."""
    data = _load()
    return list(data["completed"]) + list(data["reserved"])


def is_duplicate(topic: str) -> bool:
    data = _load()
    norm = normalize_topic(topic)
    all_used = data["completed"] + data["reserved"]
    return any(normalize_topic(t) == norm for t in all_used)


def reserve_topic(topic: str) -> str:
    """Reserve a topic. Raises DuplicateTopicError if already used/reserved."""
    if is_duplicate(topic):
        raise DuplicateTopicError(f"Topic already used or reserved: {topic}")
    data = _load()
    data["reserved"].append(topic)
    _save(data)
    return topic


def complete_topic(topic: str):
    """Move a topic from reserved -> completed. Call this after a successful upload."""
    data = _load()
    data["reserved"] = [t for t in data["reserved"] if normalize_topic(t) != normalize_topic(topic)]
    if not any(normalize_topic(t) == normalize_topic(topic) for t in data["completed"]):
        data["completed"].append(topic)
    _save(data)


def release_topic(topic: str):
    """Un-reserve a topic if the pipeline failed after reservation, so it can be retried."""
    data = _load()
    data["reserved"] = [t for t in data["reserved"] if normalize_topic(t) != normalize_topic(topic)]
    _save(data)