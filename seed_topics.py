import json
from pathlib import Path

REAL_TOPICS = [
    "Trees", "Octopus", "Ice-berg", "Dancing Bees", "World Hunger", "Volcanoes",
    "5 Facts you didn't know", "Pizza", "Dolphins", "Space", "Titanic", "Cats",
    "Sharks", "Chocolate", "Mount Everest", "Butterflies", "Harry Potter", "Coffee",
    "Bees", "Moon", "Penguins", "Volcanoes", "Dogs", "Owls", "Space Travel",
    "Dinosaurs", "Eiffel Tower", "Jellyfish", "Octopus", "Snake", "Rainbow",
    "Pyramids", "Bats", "Lightning", "Honey", "Whales", "Crows", "Camels",
    "Ice Cream", "Bamboo", "Spiders", "Elephants", "Frog", "Peacock", "Coconut",
    "Chameleon", "Meteor", "Cheese", "Wolves", "Orchids", "Clouds", "Lemurs",
    "Kangaroos", "Rainforest", "Seahorses", "Gladiators", "Jellybeans", "Axolotls",
    "Venus Flytraps", "Hedgehogs", "Coral Reefs", "Black Holes", "Sloths",
    "Mushrooms", "Hummingbirds", "Mangroves", "Koala", "Starfish", "Fireflies",
    "Platupusyes", "Komodo Dragons", "Saturn", "Falcons", "Flamingoes", "Giraffe",
    "Sea Turtles", "Camouflage", "Great Wall of China", "Santa Claus",
    "Christmas Trees", "Candy Canes", "Volcano Lightning", "Venus", "Narwhals",
    "Sand Dunes", "Pufferfish", "Parrots", "Anaconda", "Honey Badgers", "Cacti",
    "Meteor Shower", "Ice caves", "Glowworms", "Red Pandas", "Crystals", "Zebras",
    "Lava Lamps", "Dragonflies", "Puffins", "Saturn's Rings",
    "Deep Sea Hydrothermal Vents", "Bioluminescent Bays", "Aurora Borealis",
    "Amazon River", "Grand Canyon", "Jellyfish Lake", "Baobab Trees",
    "Sand Dollars", "Glass Frogs", "Fire Whirlwinds", "Ancient caves",
    "Fossilized Amber", "Sand cats", "Glass Eels", "Antarctic Icefish",
    "Andean Condor", "Bioflourescent Sharks", "Apples", "Chocolate Chips",
    "Rainbow", "Bananas", "Coffee mug", "Airplanes", "Chess", "Icebergs",
    "Fireworks", "Origami", "Bubbles", "Castles", "Hedge Mazes", "Crayons",
    "Windchimes", "Marbles", "Paperclips", "Umbrellas", "Pocket Watches",
    "Hot Air Balloons", "Zippers", "Lighthouses", "Velcro", "Echoes",
    "Tornadoes", "Rubik's cube", "Trains", "Bridges", "Escalators",
    "Leaning Tower of Pisa", "Igloos", "Boomerangs", "Snowflakes",
    "Ferris Wheeel", "Stone Globes", "Houurglasses", "Staineed Glassees",
    "Kaleidosccopes", "Lanterns", "Sundials", "Carousel", "Diving Bells",
    "Kale", "Ice skating", "Pencils", "Soap", "Ice cubes", "Sunglasses",
    "Permafrost", "Sundials", "Snow Leopards", "Moai Statues", "Leaf Insects",
    "Paper Wasps", "Mariana Trench",
]

# De-duplicate while preserving order (some topics like "Octopus", "Volcanoes",
# "Rainbow", "Sundials" appear twice in the raw list above)
seen = set()
deduped = []
for t in REAL_TOPICS:
    key = t.strip().lower()
    if key not in seen:
        seen.add(key)
        deduped.append(t)

print(f"Raw count: {len(REAL_TOPICS)}  |  Deduped count: {len(deduped)}")

topics_path = Path("database/topics.json")
videos_path = Path("database/videos.json")

topics_data = {"completed": deduped, "reserved": []}
topics_path.parent.mkdir(parents=True, exist_ok=True)
with open(topics_path, "w", encoding="utf-8") as f:
    json.dump(topics_data, f, indent=2, ensure_ascii=False)

if videos_path.exists():
    with open(videos_path, "r", encoding="utf-8") as f:
        videos_data = json.load(f)
else:
    videos_data = {"videos": []}

videos_data["next_fact_number"] = 173
with open(videos_path, "w", encoding="utf-8") as f:
    json.dump(videos_data, f, indent=2, ensure_ascii=False)

print("Seeded topics.json and set next_fact_number = 173")