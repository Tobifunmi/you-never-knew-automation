import os
from dotenv import load_dotenv
load_dotenv()

from engines.footage import search_pixabay

print("PIXABAY_API_KEY loaded:", bool(os.getenv("PIXABAY_API_KEY")))

results = search_pixabay("pangolin")
print(f"Pixabay 'pangolin' results: {len(results)}")
for hit in results[:5]:
    print(f"  id={hit.get('id')} tags='{hit.get('tags')}'")