from engines.metadata import guess_category

test_topics = [
    "Wombats",
    "Pangolins",
    "Geysers",
    "Skyscrapers",
    "Trees",
    "Space",
    "Great Wall of China",
    "Igloos",
    "Volcanoes",
    "Chess",
    "Coral Reefs",
    "Black Holes",
]

for topic in test_topics:
    print(f"{topic}: {guess_category(topic)}")