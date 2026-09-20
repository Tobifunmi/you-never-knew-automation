# You Never Knew — Automated YouTube Shorts Factory

Fully automated production and publishing pipeline for the YouTube channel
**You Never Knew** ("5 Facts You Didn't Know About [Topic]" Shorts). Topic
selection, script writing, narration, footage, captions, rendering,
metadata, YouTube upload, scheduling, and playlist assignment all run
**unattended on GitHub Actions**, triggered daily by an external scheduler.

This started as a manual-input starter project (see "Original plan" below)
but has since grown well past that — every stage listed there is done,
including full unattended scheduling. This README reflects the real
current state, not the original roadmap.

Monitor Credit Usage Here - https://you-never-knew.netlify.app/

## Current status at a glance

| Stage | Status |
|---|---|
| YouTube publisher (OAuth, upload, scheduling, playlists, DB recording) | ✅ Done |
| Narration (Kokoro-82M, local/offline, no API key or char cap) | ✅ Done |
| Footage (Pixabay → Pexels waterfall, relevance-checked, variety-enforced) | ✅ Done |
| Captions (local Whisper, burned-in ASS) | ✅ Done |
| Render (FFmpeg, 1080×1920) | ✅ Done |
| Background music (Jamendo, loops short tracks to fill narration length) | ✅ Done |
| Topic engine + fact numbering | ✅ Done |
| Autonomous topic/script generation (Gemini) | ✅ Done |
| 48h YouTube Analytics feedback loop (feeds topic selection) | ✅ Done |
| Real YouTube scheduling (`status.publishAt`, one-video-ahead buffer) | ✅ Done |
| Scheduling error handling (confirmed-missing vs. status-check-failed distinction) | ✅ Done |
| API usage dashboard (live quotas, call/video correlation, self-tracked counts) | ✅ Done |
| Full unattended automation | ✅ **Live** — see Trigger below |
| Shorts "Related video" End Screen automation | 🔜 Future work — see below |

## Scheduling

Every production run (`--production`) that has `scheduling.enabled: true`
in `config.json` uploads its video as **private with a real
`status.publishAt`** set, rather than going public immediately.
`engines/scheduling.py :: compute_next_publish_at()` decides that timestamp:

1. Looks up the most recently recorded video. If there isn't one yet (a
   genuinely fresh channel), the next video is scheduled for
   `now + cadence_hours`.
2. Otherwise, it doesn't trust the local database alone — it calls
   `publisher.get_video_status()` to ask YouTube directly what that video's
   real `privacyStatus` currently is. That call now distinguishes two
   genuinely different failure modes (see "Error handling" below): a
   confirmed-absent video (`get_video_status()` returns `None`) vs. the
   status check itself failing (`VideoStatusCheckError`, e.g. auth/quota/
   network) — these used to be conflated into the same `None` result,
   which made a real removed video indistinguishable from a transient API
   hiccup until someone dug through the traceback by hand.
3. Anchors on whichever of these is true: the video's real `publishAt` (if
   it's still scheduled/private), its real `snippet.publishedAt` (if it's
   already gone public), or `now` (if it's unlisted or was manually
   un-scheduled in Studio).
4. Cross-checks the locally recorded `scheduled_publish_at` against what
   YouTube actually reports. A mismatch (e.g. someone manually rescheduled
   the video in Studio) raises `SchedulingDriftError` rather than silently
   scheduling the next video on top of a stale assumption.
5. Returns `max(anchor, now) + cadence_hours` (currently 24h) as the next
   `publishAt`.

### Error handling: confirmed-missing vs. couldn't-check

`compute_next_publish_at()` raises one of two distinct exceptions, so the
failure email tells you which situation you're in without needing to open
the traceback:

- **`SchedulingDriftError`** — YouTube *positively confirmed* something is
  wrong: either the anchor video genuinely no longer exists there, or its
  real `publishAt` disagrees with what's locally recorded. Read: go check
  Studio, something really changed (removed/flagged video, or a manual
  edit).
- **`SchedulingStatusCheckError`** — the status check call itself failed
  (`engines/youtube.py`'s `get_video_status()` raised `VideoStatusCheckError`
  — an `HttpError` from auth, quota, or a transient network/server issue).
  Read: retry, or check credentials/quota — **not** "a video was removed."

`get_video_status()` itself only returns `None` on a genuine confirmed-absent
API response (a 200 with an empty `items` list); any `HttpError` during the
call is re-raised as `VideoStatusCheckError` rather than silently swallowed.

**Net effect**: the channel always keeps roughly one video scheduled ahead
of whatever's currently live, so a daily trigger never depends on a human
noticing an empty queue in time. `engines/youtube.py :: upload_video()`
enforces the YouTube-side rule that a `publishAt` forces `privacyStatus`
to `"private"` regardless of what was otherwise requested — YouTube itself
rejects `publishAt` on any other status.

**Known limitation, by design, not a bug**: even on a completely empty
backlog, a production run with scheduling enabled will schedule the video
`cadence_hours` out — there's no path that publishes a production video
instantly live. If the buffer is ever deliberately drained to zero and you
want the very next video to go live immediately instead of waiting a full
cadence period, that would need a small explicit change to this logic; it
doesn't happen automatically today.

## Recovering from a flagged/removed video

YouTube emails a copyright/policy notice when a published or scheduled
video gets flagged. The manual recovery (download the flagged video, swap
the background music, reupload) produces a **new video ID** — which is
exactly what breaks `compute_next_publish_at()`'s anchor, since the local
`database/videos.json` record still points at the old, now-gone ID and the
next scheduling run will raise `SchedulingDriftError` (see above).

After reuploading, hand-correct that fact's entry in `database/videos.json`
before the next run:

1. **`youtube_id`** — update to the new video's ID.
2. **`state`** — set to whatever this file uses for "scheduled, not yet
   live" (e.g. `"scheduled"`) if the reupload is scheduled rather than
   already public — a leftover pipeline-completion state like
   `"playlist_added"` misrepresents how the video actually got published.
3. **`published_at`** — clear to `null` if the video isn't live yet; the
   old value is the *deleted* video's publish time and will otherwise
   confuse Stage A0's 48h analytics gate (§ Analytics feedback loop).
4. **`scheduled_publish_at`** — set to match whatever the reupload is
   actually scheduled for in Studio (exact minute/second — the drift
   check's tolerance is only 60 seconds).
5. Manually re-add the video to the correct playlist and re-apply the
   pipeline's title/description/tags in Studio if you want it to match the
   rest of the channel's metadata conventions — none of that carries over
   from a manual reupload.

No separate automated monitoring (e.g. a daily status-sweep workflow) is
planned for catching this proactively — YouTube's own flag-notification
email already serves that purpose, and Gmail delivery of the pipeline's own
failure emails has been confirmed working, so the existing "run fails loudly,
check email" loop is considered sufficient.

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

**The 48h clock is measured from the video's actual live-publish time,
not upload-completion time.** `published_at` (set in `main.py` right
after `upload_video()` returns) only reflects when the file finished
uploading — for a scheduled video (see Scheduling above) that can be
well before it's actually public. Before counting a video eligible,
`analytics.py` confirms its real `privacyStatus` via the YouTube Data
API; a still-private/scheduled video is skipped (not "not old enough
yet" — genuinely not live). Once confirmed public, YouTube's own
`snippet.publishedAt` is cached on the record as `live_published_at`
and used for the 48h window from then on, so this only costs one
extra read call per video, the first time it's checked.

## API usage dashboard

Live at the Netlify URL above — separate repo
(`you-never-knew-dashboard`), separate deploy, separate environment
variables (Netlify env vars are NOT the same as this repo's GitHub
Secrets; both need the relevant API keys set independently).

- **Kokoro (narration)**: not a live quota check — Kokoro runs 100%
  locally with no account or cap to query. The card just reads the
  self-tracked "videos narrated" count from `usage_log.json`.
- **Pexels / Pixabay**: live quota pulled directly from each provider
  at page load, plus a self-tracked "N calls across M video(s)" note
  layered on top — useful for spotting a video that burned unusual
  credits (retries, thin footage coverage) even though the live
  percentage alone can't show that. Both checks send a random
  cache-busting query param on every request — Pexels was once
  observed serving an identical cached response (frozen rate-limit
  headers) for the check's always-identical query, making "used" look
  stuck even as real usage climbed; confirmed fixed by this cache-bust.
- **Jamendo / Gemini / YouTube Data API**: self-tracked only (these
  providers don't expose a queryable remaining-quota endpoint), read
  from `database/usage_log.json`, which every wired-in engine
  (`kokoro.py`, `footage.py`, `music.py`, `gemini.py`, `youtube.py`)
  writes to via `engines/usage_tracker.py::log_call()`.
- Every card links out to that provider's own dashboard for the
  authoritative number.

## Trigger

`daily-video.yml` only declares `workflow_dispatch:` (the manual "Run
workflow" button) as its trigger — GitHub's own `schedule:` cron is
**deliberately left commented out and unused**:

```yaml
  #schedule:
  #- cron: '0 10 * * *'
```

This is not an oversight and not a "not ready yet" placeholder — GitHub
Actions' built-in cron scheduler is known to be unreliable (delayed or
skipped runs, especially on lower-activity repos), so the actual daily
trigger comes from an external service instead: **[cron-job.org](https://cron-job.org)**
calls the workflow's `dispatches` REST API on a schedule, which GitHub
treats identically to a human clicking "Run workflow."

**cron-job.org job config**:
- URL: `https://api.github.com/repos/Tobifunmi/you-never-knew-automation/actions/workflows/daily-video.yml/dispatches`
- Method: `POST`
- Headers: `Authorization: Bearer <fine-grained GitHub PAT>`,
  `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`,
  `Content-Type: application/json`
- Body: `{"ref": "main"}`

The PAT is fine-grained, scoped to just this repo, with **Actions: Read
and write** permission, and lives only in cron-job.org's job config — never
committed here. **Check its expiration date periodically**; a lapsed token
will silently break the daily trigger with no in-repo symptom until the
Actions tab shows a gap.

If `daily-video.yml` itself is ever modified, this trigger mechanism
doesn't change — cron-job.org is calling the workflow by filename via the
API, not depending on anything inside the file except that
`workflow_dispatch:` stays declared.

## Requirements

- Windows 10/11, PowerShell
- Python 3.11+ (3.9–3.12 required specifically for Kokoro), venv at `.venv`
- ffmpeg (gyan.dev full build), on PATH
- **`espeak-ng` SYSTEM package** (not pip-installable) for Kokoro
  narration — Windows: download the `.msi` from
  [espeak-ng releases](https://github.com/espeak-ng/espeak-ng/releases)
  and run it; Linux/CI: `apt-get install espeak-ng` (already added to
  `daily-video.yml`)
- A Google Cloud project with **YouTube Data API v3** and **YouTube
  Analytics API** both enabled, OAuth 2.0 Desktop App credentials with
  the scopes in `engines/youtube.py::SCOPES` (upload + `yt-analytics.readonly`)
- **Google Auth Platform publishing status must be "In production"**, not
  "Testing" — Google forcibly expires refresh tokens after 7 days for
  apps left in Testing, which will silently break every scheduled/CI run
  once the token dies. Moving to "In production" does NOT require full
  Google verification for a personal-use app under the 100-user cap; it
  just means an "unverified app" warning screen appears on manual re-auth
  (click "Advanced" → "Go to [app name] (unsafe)" to proceed) — expected
  and harmless here, not worth pursuing full verification (CASA) for.
- API keys: `PEXELS_API_KEY`, `PIXABAY_API_KEY`, `JAMENDO_CLIENT_ID`,
  `GEMINI_API_KEY` (`ELEVENLABS_API_KEY`/`ELEVENLABS_VOICE_ID` no longer
  required — kept as GitHub Secrets harmlessly, but unused since the
  Kokoro swap)
- First run of `engines/kokoro.py` downloads ~327MB of model weights
  from Hugging Face — needs a working internet connection the first
  time only; cached afterward at `~/.cache/huggingface` (CI caches this
  directory across runs)
- `nltk` WordNet corpus (`nltk.download('wordnet')`,
  `nltk.download('omw-1.4')`) — used for free offline playlist
  categorization
- A YouTube channel with advanced features enabled (needed eventually for
  the Related Video work)
- A [cron-job.org](https://cron-job.org) account (free) if you want the
  daily trigger — see Trigger above. Not required for local/manual runs.

Do not commit:
- `credentials.json`
- `token.json` / `token.json.bak` (or any other backup/rename of the
  token file — one such file briefly entered local git history with real
  credentials inside before being caught by GitHub's push protection;
  everything matching `token.json*` should stay in `.gitignore`)
- `.env`
- API keys
- refresh tokens
- `storage_state.json` (if/when the Related Video automation lands — see below)
- Any GitHub PAT used for the cron-job.org trigger (lives only in
  cron-job.org's job config, never in this repo)

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
If a `token.json` already exists but is dead (expired/revoked), **delete
it first** — `authenticate()` tries to refresh whatever's on disk before
ever falling back to a fresh interactive login, so a dead token will
crash instead of prompting a new sign-in.

## Running the pipeline

```powershell
python main.py run test_assets\SomeScript.txt
```

Add `--production` for a real (not `unlisted`) run. This also switches
YouTube auth to fail loudly instead of hanging if `token.json` ever needs
re-authentication (important for a headless CI runner), and — if
`scheduling.enabled` is true in `config.json` — routes the upload through
the scheduler (see Scheduling above) instead of publishing immediately.

Autonomous mode (Gemini picks the topic and writes the script, no input
file) is also supported — see `main.py`'s `run` subcommand.

## Project structure

```text
you-never-knew-automation/
├── main.py                    — orchestrator, chains every pipeline stage;
│                                 Stage H computes the scheduling publish
│                                 time (if enabled) before uploading
├── config.json / config.example.json — includes a "scheduling":
│                                 {"enabled": bool, "cadence_hours": int}
│                                 block controlling the behavior above
├── requirements.txt
├── .env                       — LOCAL ONLY, gitignored
├── credentials.json           — Google OAuth desktop app credential
├── token.json                 — YouTube OAuth token, gitignored, restored
│                                 from GitHub Secret in CI
├── database/
│   ├── topics.json            — completed + reserved topics (source of truth)
│   ├── videos.json            — per-video records, keyed by fact_number;
│   │                             includes published_at (upload-completion
│   │                             time)/category (for analytics grouping),
│   │                             live_published_at (actual YouTube go-live
│   │                             time, confirmed + cached by analytics.py
│   │                             the first time a video is seen public),
│   │                             scheduled_publish_at (set when a video is
│   │                             uploaded via the scheduler, read back by
│   │                             scheduling.py on the next run to anchor
│   │                             the following video), and, once a video
│   │                             clears 48h from live_published_at, a
│   │                             performance block
│   ├── usage_log.json         — self-tracked API call counts (Jamendo/
│   │                             Gemini/YouTube/Kokoro/Pexels/Pixabay),
│   │                             written by engines/usage_tracker.py,
│   │                             read by the Netlify usage dashboard
│   └── playlists.json         — legacy, not actively used
├── engines/
│   ├── topic_engine.py        — duplicate checking, reserve/complete/release
│   ├── numbering.py           — fact number assignment, state recording,
│   │                             get_latest_video_record() (used by
│   │                             scheduling.py to find the anchor video)
│   ├── script_engine.py       — parses human-written script text files
│   ├── gemini.py              — autonomous topic + script generation,
│   │                             accepts an optional performance-context
│   │                             digest from analytics.py
│   ├── analytics.py           — 48h+ YouTube Analytics capture per video,
│   │                             builds the retention-by-category digest
│   │                             fed into gemini.py's topic prompt
│   ├── scheduling.py          — compute_next_publish_at(): decides the
│   │                             next video's status.publishAt so it lands
│   │                             cadence_hours after the latest scheduled/
│   │                             live video's real anchor time on YouTube
│   │                             (cross-checked live, not trusted from the
│   │                             local DB alone). Raises
│   │                             SchedulingDriftError if YouTube confirms
│   │                             local state is wrong (video gone, or a
│   │                             real publishAt mismatch), or
│   │                             SchedulingStatusCheckError if the status
│   │                             check call itself failed (auth/quota/
│   │                             network) — kept distinct so a failure
│   │                             email says which one happened. See
│   │                             Scheduling above.
│   ├── kokoro.py               — narration (TTS), local/offline via
│   │                             Kokoro-82M, no API key or char limit,
│   │                             logs a self-tracked "videos narrated"
│   │                             count (no credit spent, so success-only);
│   │                             requires the espeak-ng SYSTEM package
│   │                             (see Requirements below)
│   ├── elevenlabs.py          — narration (TTS), PREVIOUS engine, no
│   │                             longer imported by main.py or checked
│   │                             by the dashboard, kept as an easy
│   │                             rollback path (swap one import + one
│   │                             filename in main.py to revert)
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
│   │                             loops short tracks to fill narration length;
│   │                             VIBE_MAP tags are space-separated (not
│   │                             "+"-joined) — requests percent-encodes a
│   │                             literal "+" in a params value, which
│   │                             Jamendo then reads back as one literal
│   │                             "tag+tag" tag instead of two tags
│   ├── usage_tracker.py       — writes database/usage_log.json;
│   │                             log_call(service, fact_number=...)
│   │                             correlates calls to the video that made them
│   └── youtube.py              — upload (with optional publish_at for
│                                  scheduling), get_video_status() (real
│                                  Data API status/snippet lookup, used by
│                                  scheduling.py to verify local state;
│                                  returns None only on a confirmed-absent
│                                  video, raises VideoStatusCheckError if
│                                  the API call itself fails), playlist
│                                  management, retry logic, OAuth scopes
│                                  (upload + Analytics readonly)
├── test_assets/                — sample scripts
├── work/Fact_NNN_slug/          — per-video working directory
└── .github/workflows/
    └── daily-video.yml         — only workflow_dispatch is declared; the
                                   daily trigger comes from cron-job.org
                                   calling that endpoint on a schedule, not
                                   from a schedule: block in this file —
                                   see Trigger above
```

## Known limitations (accepted, not bugs to chase)

- **A production run with scheduling enabled never publishes instantly
  live, even on a completely empty backlog.** `compute_next_publish_at()`
  always returns `now + cadence_hours` at minimum — see Scheduling above.
  Intentional (protects against a slow pipeline run leaving a same-day
  gap), but worth knowing if the buffer is ever deliberately drained.
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
- **Jamendo's free-tier terms are non-commercial-use only.** This is
  fine while the channel isn't monetized/in YPP, but MUST be revisited
  (Jamendo license filtering) the moment monetization status changes —
  not forgotten, deliberately deferred. Narration is no longer part of
  this concern: Kokoro's weights are Apache-2.0, commercial-use-safe
  regardless of monetization status.
- **`engines/gemini.py` validates scripts independently** rather than
  reusing `script_engine.parse_script()` — both define the same script
  dict shape but as separate code paths. If that shape ever changes,
  both need updating.
- **A `requests` `params` dict silently mangles literal "+" characters.**
  `VIBE_MAP` tag values used to be written `"cinematic+ambient"`,
  following Jamendo's documented `+`-as-separator format for multi-value
  params. But `requests` percent-encodes a literal `+` in a params dict
  value to `%2B` (to disambiguate it from an encoded space), which
  Jamendo decodes back to a literal `+` and searches for one tag named
  `"cinematic+ambient"` — which doesn't exist — instead of the two tags
  `cinematic` and `ambient`. Net effect: every topic-specific ("Tier 1")
  Jamendo search silently returned zero results from the start, and
  every video's music fell through to the generic single-tag
  `"cinematic"` fallback regardless of actual topic/vibe — not a crash,
  just quietly never doing what `VIBE_MAP` was there to do. Fixed by
  using a plain space instead (`requests` encodes that to a raw `+` on
  the wire, matching Jamendo's actual expected format). Worth
  remembering for any other multi-value Jamendo/similar API param added
  later — don't hand-write the `+` yourself, let the space do it.
- **The 48h analytics performance snapshot is captured once, not
  continuously refreshed.** A video's `performance` block reflects
  cumulative stats at the moment it first crossed 48h old — later
  views don't update it. This is a deliberate "how did it land"
  snapshot, not a live number. The category-retention digest fed to
  Gemini also stays silent (empty string, no prompt change) until at
  least 3 videos have a captured snapshot, to avoid skewing topic
  choice off one or two data points.
- **A GitHub Auth header value needs `Bearer <token>` exactly** — an
  extra colon (`Bearer: <token>`) is invalid and produces a `401` from
  GitHub's API even though the token itself is fine. Easy to mistype
  when setting up or rotating the cron-job.org PAT.

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
those stages are now built, including full unattended daily automation;
this section is kept only as historical context for why the architecture
looks the way it does.
