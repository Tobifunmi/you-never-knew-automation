# You Never Knew — Automated YouTube Shorts Factory

Fully automated production and publishing pipeline for the YouTube channel
**You Never Knew** ("5 Facts You Didn't Know About [Topic]" Shorts). Topic
selection, script writing, narration, footage, captions, rendering,
metadata, YouTube upload, and playlist assignment all run **unattended on
GitHub Actions**.

This started as a manual-input starter project (see "Original plan" below)
but has since grown well past that — most stages listed there are done.
This README reflects the real current state, not the original roadmap.

Monitor Credit Usage Here - https://you-never-knew.netlify.app/

## Current status at a glance

| Stage | Status |
|---|---|
| YouTube publisher (OAuth, upload, playlists, DB recording) | ✅ Done |
| Narration (ElevenLabs) | ✅ Done |
| Footage (Pixabay → Pexels waterfall, relevance-checked, variety-enforced) | ✅ Done |
| Captions (local Whisper, burned-in ASS) | ✅ Done |
| Render (FFmpeg, 1080×1920) | ✅ Done |
| Background music (Jamendo, loops short tracks to fill narration length) | ✅ Done |
| Topic engine + fact numbering | ✅ Done |
| Autonomous topic/script generation (Gemini) | ✅ Done |
| 48h YouTube Analytics feedback loop (feeds topic selection) | ✅ Done |
| API usage dashboard (live quotas, call/video correlation, self-tracked counts) | ✅ Done |
| Full unattended automation (GitHub Actions) | ✅ Done, `workflow_dispatch`; scheduled cron (Mon/Thu) added but verify enabled |
| Shorts "Related video" End Screen automation | 🔜 Future work — see below |

## Analytics feedback loop

Every run starts with **Stage A0**, before topic selection: `engines/analytics.py`
scans `database/videos.json` for any video that's crossed 48 hours since
publish and doesn't have performance data yet, pulls its cumulative
views/retention from the **YouTube Analytics API**, and writes it back
into that video's record. Once at least 3 videos have this captured, a
short retention-by-category digest gets appended to the Gemini topic
prompt as a soft nudge — it leans topic selection toward categories
that have retained viewers well, without ever overriding the
exclusion/variety rules.

This requires the **`yt-analytics.readonly`** OAuth scope in addition
to the original upload scope (see `SCOPES` in `engines/youtube.py`). A
`token.json` minted before this was added needs **one fresh interactive
re-auth** (`python main.py auth`) to pick up the new scope — Google
won't silently widen an existing token's permissions. After re-auth,
update the `YOUTUBE_TOKEN_JSON` GitHub Secret with the new token so CI
runs pick it up too.

This never blocks a real video: every function in `analytics.py`
swallows its own errors and logs a message rather than raising, so a
missing scope, a Google API hiccup, or no eligible videos yet just
means "no context this run" — not a pipeline failure.

## API usage dashboard

Live at the Netlify URL above — separate repo
(`you-never-knew-dashboard`), separate deploy, separate environment
variables (Netlify env vars are NOT the same as this repo's GitHub
Secrets; both need the relevant API keys set independently).

- **ElevenLabs / Pexels / Pixabay**: live quota pulled directly from
  each provider at page load, plus a self-tracked "N calls across M
  video(s)" note layered on top — useful for spotting a video that
  burned unusual credits (retries, long scripts) even though the live
  percentage alone can't show that.
- **Jamendo / Gemini / YouTube Data API**: self-tracked only (these
  providers don't expose a queryable remaining-quota endpoint), read
  from `database/usage_log.json`, which every wired-in engine
  (`elevenlabs.py`, `footage.py`, `music.py`, `gemini.py`, `youtube.py`)
  writes to via `engines/usage_tracker.py::log_call()`.
- Every card links out to that provider's own dashboard for the
  authoritative number.

## Trigger

Currently `workflow_dispatch` (manual). A `schedule` cron for **Monday and
Thursday** has been added to `daily-video.yml`:

```yaml
schedule:
  - cron: '0 10 * * 1,4'
```

Confirm this is actually uncommented/active before relying on it to run
unattended — check the workflow file directly rather than assuming.

## Requirements

- Windows 10/11, PowerShell
- Python 3.11+, venv at `.venv`
- ffmpeg (gyan.dev full build), on PATH
- A Google Cloud project with **YouTube Data API v3** and **YouTube
  Analytics API** both enabled, OAuth 2.0 Desktop App credentials with
  the scopes in `engines/youtube.py::SCOPES` (upload + `yt-analytics.readonly`)
- API keys: `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID`, `PEXELS_API_KEY`,
  `PIXABAY_API_KEY`, `JAMENDO_CLIENT_ID`, `GEMINI_API_KEY`
- `nltk` WordNet corpus (`nltk.download('wordnet')`,
  `nltk.download('omw-1.4')`) — used for free offline playlist
  categorization
- A YouTube channel with advanced features enabled (needed eventually for
  the Related Video work)

Do not commit:
- `credentials.json`
- `token.json`
- `.env`
- API keys
- refresh tokens
- `storage_state.json` (if/when the Related Video automation lands — see below)

## Install

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -c "import nltk; nltk.download('wordnet'); nltk.download('omw-1.4')"
```

Copy `config.example.json` → `config.json`. Put Google OAuth desktop
credentials in `credentials.json`. Put the API keys above into `.env`
(local only, gitignored — in CI these come from GitHub Secrets instead).

Then run:

```powershell
python main.py auth
```

The first run opens Google's OAuth consent screen and creates `token.json`.

## Running the pipeline

```powershell
python main.py run test_assets\SomeScript.txt
```

Add `--production` for a real (not `unlisted`) run — this also switches
YouTube auth to fail loudly instead of hanging if `token.json` ever needs
re-authentication, since that would otherwise hang a headless CI runner
indefinitely.

Autonomous mode (Gemini picks the topic and writes the script, no input
file) is also supported — see `main.py`'s `run` subcommand.

## Project structure

```text
you-never-knew-automation/
├── main.py                    — orchestrator, chains every pipeline stage
├── config.json / config.example.json
├── requirements.txt
├── .env                       — LOCAL ONLY, gitignored
├── credentials.json           — Google OAuth desktop app credential
├── token.json                 — YouTube OAuth token, gitignored, restored
│                                 from GitHub Secret in CI
├── database/
│   ├── topics.json            — completed + reserved topics (source of truth)
│   ├── videos.json            — per-video records, keyed by fact_number;
│   │                             includes published_at/category (for
│   │                             analytics grouping) and, once a video
│   │                             clears 48h, a performance block
│   ├── usage_log.json         — self-tracked API call counts (Jamendo/
│   │                             Gemini/YouTube/ElevenLabs/Pexels/Pixabay),
│   │                             written by engines/usage_tracker.py,
│   │                             read by the Netlify usage dashboard
│   └── playlists.json         — legacy, not actively used
├── engines/
│   ├── topic_engine.py        — duplicate checking, reserve/complete/release
│   ├── numbering.py           — fact number assignment, state recording
│   ├── script_engine.py       — parses human-written script text files
│   ├── gemini.py              — autonomous topic + script generation,
│   │                             accepts an optional performance-context
│   │                             digest from analytics.py
│   ├── analytics.py           — 48h+ YouTube Analytics capture per video,
│   │                             builds the retention-by-category digest
│   │                             fed into gemini.py's topic prompt
│   ├── elevenlabs.py          — narration (TTS)
│   ├── captions.py            — Whisper word timestamps, ASS caption files
│   ├── timeline.py            — maps script segments to audio time ranges
│   ├── footage.py             — Pixabay → Pexels waterfall w/ relevance +
│   │                             variety enforcement, generic scenery as
│   │                             a last-resort (non-relevance-checked) fallback
│   ├── renderer.py             — normalize/concat/burn-in captions (FFmpeg)
│   ├── metadata.py            — title/description/tags, WordNet-based
│   │                             playlist categorization (scans every
│   │                             word in the topic, not just the first)
│   ├── music.py               — Jamendo background track fetch + mix,
│   │                             loops short tracks to fill narration length
│   ├── usage_tracker.py       — writes database/usage_log.json;
│   │                             log_call(service, fact_number=...)
│   │                             correlates calls to the video that made them
│   └── youtube.py              — upload, playlist management, retry logic,
│                                  OAuth scopes (upload + Analytics readonly)
├── test_assets/                — sample scripts
├── work/Fact_NNN_slug/          — per-video working directory
└── .github/workflows/
    └── daily-video.yml
```

## Known limitations (accepted, not bugs to chase)

- **WordNet categorization** now scans every non-stopword word in the
  topic (not just the first) and has landmark/element/geological-feature
  keyword coverage, so multi-word proper nouns like "The Dead Sea" or
  "Giant's Causeway" resolve correctly rather than falling through to
  the generic "Amazing Facts" category (verified against full history:
  0/13 defaulted, was 6/13 before the fix). Rare single-word sense
  ambiguity can still misfire (e.g. "Chess" resolves to a WordNet
  plant sense before the board-game sense) — accepted, not worth a new
  playlist category for one word. Occasional keyword-dict additions are
  fine as ordinary maintenance; AI-based classification was explicitly
  rejected on cost/pattern grounds.
- **`footage.py`'s generic fallback** (`"nature landscape"` / `"scenery"`)
  has no topic-relevance check and will succeed silently rather than
  failing loudly. This only bites when a topic has genuinely thin stock
  footage coverage (e.g. Wombats originally) — worth spot-checking the
  footage source report on niche topics.
- **Jamendo and ElevenLabs free-tier terms are non-commercial-use only.**
  This is fine while the channel isn't monetized/in YPP, but MUST be
  revisited (Jamendo license filtering, ElevenLabs plan tier) the moment
  monetization status changes — not forgotten, deliberately deferred.
- **`engines/gemini.py` validates scripts independently** rather than
  reusing `script_engine.parse_script()` — both define the same script
  dict shape but as separate code paths. If that shape ever changes,
  both need updating.
- **The 48h analytics performance snapshot is captured once, not
  continuously refreshed.** A video's `performance` block reflects
  cumulative stats at the moment it first crossed 48h old — later
  views don't update it. This is a deliberate "how did it land"
  snapshot, not a live number. The category-retention digest fed to
  Gemini also stays silent (empty string, no prompt change) until at
  least 3 videos have a captured snapshot, to avoid skewing topic
  choice off one or two data points.

## Future work — Shorts "Related Video" (End Screen)

YouTube's official Data API does not expose the Studio "Related video" /
End Screen setting as a normal metadata field, so this can't be done
through the API layer the rest of this pipeline uses. A Playwright-based
Studio browser-automation approach (scripted login session, drive the End
Screen editor UI directly) was scoped out and prototyped, but shelved for
now — real UI automation against a login-gated, API-less surface is
meaningfully more fragile than everything else in this pipeline, and it
wasn't worth committing to before revisiting. Two paths remain open
whenever this gets picked back up:

- Playwright/Studio End Screen automation (prototyped, needs a supervised
  headed run to validate selectors against the current Studio UI before
  it could be trusted unattended)
- A simpler, non-browser-automation alternative — e.g. a link in the video
  description instead of a Studio End Screen element

Either way, the rule (always link to the immediately-previous fact video)
is already decided; it's just the mechanism left open.

## Original plan (superseded, kept for history)

The project originally started as a smaller starter architecture — publish
an existing test MP4 first, then layer in voice/footage/captions/render/
topic-generation/automation one stage at a time (V0.1 through V0.6). That
sequencing is why the engine files are separated the way they are. All of
those stages are now built; this section is kept only as historical
context for why the architecture looks the way it does.
