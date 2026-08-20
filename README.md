# You Never Knew — Automated YouTube Shorts Factory

This is the starter architecture for automating the "You Never Knew" workflow:

1. Receive a topic/script
2. Assign the next `Fact N` number
3. Generate the YouTube title/description metadata
4. Generate voiceover (planned)
5. Find stock footage (planned)
6. Generate captions (planned)
7. Render 9:16 video (planned)
8. Upload to YouTube
9. Put the video in the appropriate playlist
10. Record the topic/video in the local database
11. Later: automate the Shorts "Related video" Studio setting

## Important

The current version deliberately separates the YouTube publishing layer from the video-generation layer. We can test publishing with any existing MP4 before wiring in ElevenLabs/Pexels/FFmpeg.

Do not commit:
- `credentials.json`
- `token.json`
- `.env`
- API keys
- refresh tokens

## Requirements

- Windows 10/11
- Python 3.11+
- A Google Cloud project with YouTube Data API v3 enabled
- OAuth 2.0 Desktop App credentials
- A YouTube channel with advanced features enabled if you intend to use Shorts' Related Video feature

## Install

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy:

```text
config.example.json -> config.json
```

Put your Google OAuth desktop credentials in:

```text
credentials.json
```

Then run:

```powershell
python main.py --auth
```

The first run opens Google's OAuth consent screen and creates `token.json`.

## Test the YouTube publisher

Put an existing MP4 in:

```text
test_assets\test.mp4
```

Then:

```powershell
python main.py --upload-test test_assets\test.mp4
```

The starter defaults to `unlisted` so we can test safely.

## Project structure

```text
you-never-knew-automation/
├── main.py
├── config.example.json
├── requirements.txt
├── .gitignore
├── database/
│   ├── topics.json
│   ├── videos.json
│   └── playlists.json
├── engines/
│   ├── __init__.py
│   ├── metadata.py
│   ├── memory.py
│   └── youtube.py
├── test_assets/
│   └── .gitkeep
└── .github/
    └── workflows/
        └── daily-video.yml
```

## Next implementation stages

### V0.1 — YouTube publisher
- OAuth
- upload
- title
- description
- tags
- playlist selection/creation
- database recording

### V0.2 — Voice
- ElevenLabs API
- fixed channel voice
- audio duration

### V0.3 — Footage
- Pexels video search
- portrait-first filtering
- multiple shots per fact

### V0.4 — Captions/render
- word/phrase timing
- FFmpeg/Remotion
- 1080x1920
- background music
- channel caption style

### V0.5 — Topic engine
- read used-topic database
- generate a new unused topic
- fact-number assignment
- topic quality/duplication checks

### V0.6 — Full automation
- GitHub Actions schedule
- YouTube OAuth refresh token in GitHub Secrets
- automatic publishing
- playlist creation
- persistent database
- retry/recovery

### V0.7 — Shorts Related Video
The official YouTube Data API does not currently expose the Studio "Related video" field as a normal video metadata property. We will investigate a browser-automation last-mile step after the official API pipeline is stable.
