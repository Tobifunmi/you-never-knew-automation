from engines.youtube import YouTubePublisher

yt = YouTubePublisher()
yt.authenticate()

playlist_id = yt.find_or_create_playlist("Nature Facts", auto_create=True)
print("Playlist ID:", playlist_id)