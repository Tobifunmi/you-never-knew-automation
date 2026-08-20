from engines.youtube import YouTubePublisher

yt = YouTubePublisher()
yt.authenticate()

playlists = yt.list_playlists()
print(f"Found {len(playlists)} playlists:")
for p in playlists:
    print(f"  - {p['snippet']['title']} (id: {p['id']})")