from __future__ import annotations
from nltk.corpus import wordnet as wn

import re
import nltk


CATEGORY_KEYWORDS = {
    "Nature Facts": [
        "plant", "animal", "insect", "bird", "fish", "tree", "flower", "forest",
        "ocean", "sea", "jungle", "reef", "mammal", "reptile", "amphibian", "shark",
        "dolphin", "whale", "spider", "bee", "butterfly", "frog", "snake",
        "coral", "leaf", "wildlife", "rainforest", "predator", "prey",
        "lake", "river", "waterfall", "glacier", "volcano", "canyon", "desert",
        "island", "cave", "salt flat", "salar", "geyser", "dune",
        "bermuda triangle",
    ],
    "Space Facts": [
        "space", "planet", "star", "moon", "sun", "galaxy", "asteroid",
        "comet", "black hole", "nebula", "astronaut", "nasa", "meteor",
        "solar", "cosmic", "universe", "saturn", "venus",
    ],
    "History Facts": [
        "ancient", "pyramid", "empire", "war", "castle", "medieval",
        "civilization", "historical", "gladiator", "titanic", "ruins",
        "tomb", "mausoleum", "dynasty",
    ],
    "Architecture & Structures Facts": [
        "skyscraper", "cathedral", "temple", "tower", "bridge", "causeway",
        "statue", "monument", "palace", "fort", "fortress", "wall", "dam",
        "stadium", "lighthouse", "mahal",
    ],
    "Science & Technology Facts": [
        "physics", "chemistry", "technology", "engineering", "invention",
        "machine", "robot", "computer", "electricity", "gravity",
        "neon", "element", "chemical",
    ],
    "Everyday Objects Facts": [
        "pencil", "umbrella", "zipper", "clock", "mirror", "candle",
        "button", "paperclip", "soap", "sunglasses",
    ],
}
DEFAULT_CATEGORY = "Amazing Facts"

# Maps broad WordNet hypernym concepts to your playlist categories.
# Checked in order; first match wins.
HYPERNYM_CATEGORY_MAP = [
    ("celestial_body.n.01", "Space Facts"),
    ("star.n.01", "Space Facts"),
    ("planet.n.01", "Space Facts"),
    ("chemical_element.n.01", "Science & Technology Facts"),
    ("animal.n.01", "Nature Facts"),
    ("plant.n.02", "Nature Facts"),
    ("geological_formation.n.01", "Nature Facts"),
    ("natural_phenomenon.n.01", "Nature Facts"),
    ("body_of_water.n.01", "Nature Facts"),
    ("structure.n.01", "Architecture & Structures Facts"),
    ("building.n.01", "Architecture & Structures Facts"),
    ("road.n.01", "Architecture & Structures Facts"),
    ("sculpture.n.01", "Architecture & Structures Facts"),
    ("instrumentality.n.03", "Everyday Objects Facts"),
    ("machine.n.01", "Science & Technology Facts"),
]

# Words too generic/grammatical to carry any topic signal — skipped in the
# WordNet fallback so e.g. "The Dead Sea" doesn't get stuck checking "The".
_STOPWORDS = {
    "the", "a", "an", "of", "de", "la", "le", "el", "du", "von", "van", "and",
}

def _singularize(word: str) -> str:
    """Lightweight English depluralizer — handles common suffix patterns
    better than a blind rstrip('s')."""
    word = word.lower()
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith(("oes", "xes", "ses", "ches", "shes")) and len(word) > 4:
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def _wordnet_category(topic: str) -> str | None:
    """
    Free, offline fallback for when the keyword dict misses. Multi-word
    topics are common here ("The Dead Sea", "Giant's Causeway", "The
    Statue of Liberty") and the category-bearing word is often NOT the
    first one — articles ("The") carry no signal, and even content words
    can be the wrong ones ("Giant's" in "Giant's Causeway"). So this
    checks every non-stopword word in the topic, left to right, and
    returns the first one whose hypernym chain matches a known category
    — not just the first word overall.

    For each word, checks the first several WordNet noun senses (not
    just the single most-common sense, since that's sometimes the wrong
    one — e.g. "volcano"'s top sense is an unrelated 'vent' meaning).
    No API calls, no cost. Rare ambiguous words (e.g. "chess") can still
    resolve to an unrelated sense; this is an accepted limitation.
    """
    words = re.findall(r"[A-Za-z]+", topic)
    candidates = [_singularize(w) for w in words if w.lower() not in _STOPWORDS]

    for word in candidates:
        synsets = wn.synsets(word, pos=wn.NOUN)
        if not synsets:
            continue
        for synset in synsets[:5]:
            hypernym_names = {s.name() for path in synset.hypernym_paths() for s in path}
            hypernym_names.add(synset.name())
            for concept, category in HYPERNYM_CATEGORY_MAP:
                if concept in hypernym_names:
                    return category

    return None


def guess_category(topic: str) -> str:
    """
    First tries a fast hand-maintained keyword match (cheap, no dependency
    needed). Falls back to a free offline WordNet lookup for topics the
    keyword list doesn't recognize, before finally giving up to the
    default catch-all category. No AI calls anywhere in this function.
    """
    topic_lower = topic.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in topic_lower for kw in keywords):
            return category

    wordnet_result = _wordnet_category(topic)
    if wordnet_result:
        return wordnet_result

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