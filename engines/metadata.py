from __future__ import annotations

import re

CATEGORY_KEYWORDS = {
    "Nature Facts": [
        "plant", "animal", "insect", "bird", "fish", "tree", "flower", "forest",
        "ocean", "jungle", "reef", "mammal", "reptile", "amphibian", "shark",
        "dolphin", "whale", "spider", "bee", "butterfly", "frog", "snake",
        "coral", "leaf", "wildlife", "rainforest", "predator", "prey",
    ],
    "Space Facts": [
        "space", "planet", "star", "moon", "sun", "galaxy", "asteroid",
        "comet", "black hole", "nebula", "astronaut", "nasa", "meteor",
        "solar", "cosmic", "universe", "saturn", "venus",
    ],
    "History Facts": [
        "ancient", "pyramid", "empire", "war", "castle", "medieval",
        "civilization", "historical", "gladiator", "titanic", "ruins",
    ],
    "Science & Technology Facts": [
        "physics", "chemistry", "technology", "engineering", "invention",
        "machine", "robot", "computer", "electricity", "gravity",
    ],
    "Everyday Objects Facts": [
        "pencil", "umbrella", "zipper", "clock", "mirror", "candle",
        "button", "paperclip", "soap", "sunglasses",
    ],
}

DEFAULT_CATEGORY = "Amazing Facts"


def guess_category(topic: str) -> str:
    """
    TEMPORARY stopgap keyword-based category guesser. Crude but functional;
    should eventually be replaced by an AI classification call, per the
    project's principle that categorization is a creative decision, not
    a deterministic one. Also used by Stage H for playlist matching.
    """
    topic_lower = topic.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in topic_lower for kw in keywords):
            return category
    return DEFAULT_CATEGORY


def make_title(fact_number: int, topic: str, template: str) -> str:
    return template.format(fact_number=fact_number, topic=topic)


def hashtags(topic: str, category: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", topic)
    topic_tag = "".join(w.capitalize() for w in words[:4]) or "Facts"
    category_tag = "#" + category.replace(" & ", "").replace(" ", "")
    return f"#{topic_tag} {category_tag} #Facts #YouNeverKnew"


def make_description(topic: str, intro: str, category: str) -> str:
    topic_lower = topic.lower()
    return (
        f"{intro.strip()}\n\n"
        f"In this video, discover 5 fascinating facts about {topic_lower} "
        f"that will completely change the way you look at {topic_lower} forever!\n\n"
        f"Subscribe to You Never Knew for more incredible facts, and share in the comments: "
        f"Which {topic_lower} fact amazed you the most?\n\n"
        f"{hashtags(topic, category)}"
    )


def make_metadata(
    fact_number: int,
    topic: str,
    intro: str,
    title_template: str,
) -> dict:
    category = guess_category(topic)
    return {
        "title": make_title(fact_number, topic, title_template),
        "description": make_description(topic, intro, category),
        "category": category,
        "tags": [
            topic,
            f"{topic} facts",
            "5 facts",
            "interesting facts",
            f"{category.lower()}",
            "science facts",
            "You Never Knew",
        ],
    }