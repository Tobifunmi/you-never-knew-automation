# MASTER CONTINUATION PROMPT — "You Never Knew" Automated YouTube Shorts Factory

Use this as full context in a new conversation. Reflects the actual
verified state of the project as of **27 Aug 2026** — several things
below were only discovered to be wrong (not just undone) by reading
real files directly, so treat this as ground truth over any older
summary, including any earlier version of this same document.

GitHub username: **Tobifunmi** (capitalized — the automation repo's
remote previously pointed at the old lowercase `tobifunmi` URL and
GitHub silently redirected; worth double-checking both repos' remotes
use the current casing to avoid relying on a redirect indefinitely).
Automation repo: `github.com/Tobifunmi/you-never-knew-automation`
(public). Dashboard repo: `github.com/Tobifunmi/you-never-knew-dashboard`
(public). Live dashboard: `https://you-never-knew.netlify.app/`.

Local dev machine: Windows 10/11, PowerShell, two separate local repo
folders — `C:\Users\user\Documents\You Never Knew` (automation) and
`C:\Users\user\Documents\You Never Knew - Dashboard` (dashboard).

---

## 1. What this project is

A fully automated production and publishing pipeline for the YouTube
channel **You Never Knew** — "5 Facts You Didn't Know About [Topic]"
YouTube Shorts. Topic selection, script writing, narration, footage,
captions, rendering, background music, metadata, YouTube upload,
playlist assignment, database recording, 48h+ performance tracking, and
failure notification all run on GitHub Actions (when triggered — see
§9 on cron status). Runs locally on Windows for development/testing.

---

## 2. Current status

| Stage | Status |
|---|---|
| YouTube publisher (OAuth, upload, playlists, DB recording) | ✅ Done |
| Narration (ElevenLabs, "Adam" voice, free tier) | ✅ Done |
| Footage (Pixabay → Pexels waterfall) | ✅ Done |
| Captions (local Whisper, burned-in ASS) | ✅ Done |
| Render (FFmpeg, 1080×1920) | ✅ Done |
| Background music (Jamendo, loops short tracks, blocklist-aware) | ✅ Done |
| Topic engine + fact numbering | ✅ Done |
| Autonomous topic/script generation (Gemini) | ✅ Done, audited |
| **48h YouTube Analytics feedback loop** (Stage A0, feeds topic selection) | ✅ Done, NEW this session |
| **Category-guessing fix** (WordNet: scans every word, not just the first) | ✅ Done, NEW this session — verified 0/13 fall to default (was 6/13) |
| **Usage dashboard: call/video correlation + hyperlinks** | ✅ Done, NEW this session |
| Full unattended automation (GitHub Actions) | ⚠️ **Cron deliberately still commented out** — `workflow_dispatch` (manual button) only. This is an explicit choice, not an oversight — do not silently re-enable it. |
| Email failure notifications (Gmail SMTP) | ✅ Done, tested, confirmed firing correctly on a real transient failure |
| Playlist/record ordering bug | ✅ Fixed |
| API usage dashboard (local script) | ✅ Done — `check_usage.py` |
| API usage dashboard (public, live, Netlify-hosted) | ✅ Done — `you-never-knew.netlify.app`, now with clickable links + call/video correlation |
| Per-video Jamendo track ID/name recording | ✅ Done |
| Persistent Jamendo track blocklist | ✅ Done, built but not yet populated |
| **CI secret name mismatch** (workflow read `TOKEN_JSON`, secret was named `YOUTUBE_TOKEN_JSON`) | ✅ Fixed this session — workflow now reads `secrets.YOUTUBE_TOKEN_JSON` |
| Wombats (Fact 174) footage repetition | ✅ Fixed (historical) |
| Pangolins (Fact 175) bad-footage database record | ✅ Fixed (historical) |
| Statue of Liberty (Fact 180) Content ID claim | ✅ Resolved manually (historical, see §5 item 11) |
| Shorts "Related video" End Screen | 🔜 Deliberately deferred |

---

## 3. Pipeline stages, actual execution order (`main.py` `run_pipeline()`)

0. **Config load** — `config.json`. Key fields: `starting_fact_number:
   172`, `title_template: "Fact {fact_number}: 5 Facts You Didn't Know
   About {topic}"`, `youtube.privacy_status: "unlisted"`,
   `youtube.category_id: "27"` (Education), `youtube.auto_create_playlists:
   true`.
1. **Stage A0 — 48h+ performance capture (NEW).** `engines/analytics.py
   :: update_performance_log(publisher)` runs FIRST, before topic
   selection. Scans `database/videos.json` for any video with a
   `youtube_id` + `published_at` that's ≥48h old and has no
   `performance` block yet, pulls cumulative
   views/likes/comments/averageViewPercentage/estimatedMinutesWatched
   via the **YouTube Analytics API** (`youtubeAnalytics/v2`,
   `reports().query()`), writes it back into that video's record.
   Walks the WHOLE list each run (not just the latest video), so a
   missed video from a paused run still gets caught. Once ≥3 videos
   have captured performance, `build_performance_context()` produces a
   retention-by-category digest fed into the next step. Never raises —
   every function swallows its own errors and logs a message; a
   missing scope or API hiccup just means "no context this run."
   Requires the `yt-analytics.readonly` OAuth scope (added alongside
   the original upload scope in `engines/youtube.py::SCOPES`).
   `YouTubePublisher` is now instantiated and authenticated at this
   early point (moved up from Stage H) specifically so this step can
   reuse the same OAuth session — `publisher.credentials` is exposed
   for this reuse.
2. **Stage A/B — Topic + script ingestion.** Manual (`script_path`
   given, `script_engine.parse_script()`, duplicate check aborts via
   `SystemExit`) or autonomous (`gemini.get_unique_topic(performance_context=...)`
   + `gemini.generate_script()`). The performance context from Stage
   A0 is a soft nudge only — appended to the Gemini prompt, told to
   "lean toward" higher-retention categories without abandoning
   others; never overrides the topic exclusion/variety rules.
   `numbering.get_next_fact_number()` assigns the fact number.
   `topic_engine.reserve_topic()` (reservation, not completion). This
   entire stage (plus Stage A0) is inside the pipeline's `try` block,
   guarded by a `topic_reserved` flag for the failure path.
3. **Stage C — Narration** (ElevenLabs, `engines/elevenlabs.py`, voice
   "Adam", free tier). Every call is logged via
   `usage_tracker.log_call("elevenlabs", fact_number=script["fact_number"])`
   regardless of success/failure — correlates ElevenLabs credit usage
   to the specific video it was for.
4. **Transcription** — local Whisper, free regardless of narration source.
5. **Timeline** — `timeline.build_segment_timeline()`, word-count
   alignment between script and Whisper output.
6. **Stage D — Footage** (`engines/footage.py`). Pixabay specific →
   Pexels specific → Pixabay broad topic fallback → Pexels broad topic
   fallback → generic "nature landscape"/"scenery" (no relevance
   check, last resort). `exclude_ids` enforces variety across the 5
   facts within one video. Every Pexels/Pixabay search call is logged
   via `usage_tracker.log_call(..., fact_number=video_id)`, where
   `video_id` is the whole video's `fact_number` (not the per-fact
   index within it) threaded through `download_footage_for_script()` →
   `download_footage_for_prompt()` → the individual
   `_download_from_pexels`/`_download_from_pixabay` helpers.
7. **Stage E — Captions file** (ASS).
8. **Stage F — Render.** `normalize_all_segments()` →
   `concatenate_segments()` → background music fetch/mix →
   `burn_in_captions()`.
   - Music: `music.fetch_and_download_background_track()` returns a
     **dict** (`path`, `track_id` namespaced as `"jamendo:<id>"`,
     `track_name`, `track_url`), not a bare path string. Prefers a
     track ≥ narration length; falls back to the longest track ≥15s
     (`MIN_LOOPABLE_DURATION = 15.0`) and loops it via ffmpeg
     `-stream_loop -1` in `mix_background_music()`. Filters out
     anything in the persistent blocklist
     (`database/music_blocklist.json`) before selection. `_query()`
     checks Jamendo's own `headers.status` field and raises a specific
     error with Jamendo's real error message if the API call itself
     failed (quota/rate-limit/etc.) — previously silently
     indistinguishable from "no tracks match" (see §5 item 12).
9. **Stage G — Metadata.** Title/description/tags, WordNet-based
   playlist categorization (offline, free). **Rewritten this session**
   — see §4 for the specifics; short version: scans every non-stopword
   word in the topic (not just the first), fixing multi-word proper
   nouns like "The Dead Sea" and "Giant's Causeway" that used to fall
   through to the generic "Amazing Facts" category.
10. **Stage H — Upload.** `unlisted` unless `--production`. `published_at`
    is captured immediately after upload (`datetime.now(timezone.utc)`,
    approximated as upload time, not the actual YouTube-reported
    publish timestamp — accurate to within a few seconds since it's
    recorded right after the upload call returns).
11. **Record + complete topic.** Runs **immediately after upload
    succeeds, before the playlist step** (deliberate, load-bearing
    ordering — see §5 item 1). Records `music_track_id`,
    `music_track_name`, `published_at`, and `category` (from
    `metadata["category"]`) alongside the existing fields.
12. **Stage I — Playlist.** Isolated `try/except`. Success →
    `record_video_state()` called again (safe, merges by `fact_number`)
    with real `playlist_id` and `state="playlist_added"` (also
    re-passes `published_at`/`category`). Failure → sends a failure
    email, prints a warning, does **not** re-raise — video is already
    safely recorded.
13. **Failure path** (any stage): outer `except Exception`. Sends a
    detailed failure email via `engines/notifications.py` (Gmail SMTP,
    App Password auth) with current stage, error, fact/topic if known,
    mode, full traceback. Releases the topic reservation only if it
    was actually reserved. Confirmed working in production on a real
    transient Jamendo failure.

---

## 4. Category-guessing fix (this session, `engines/metadata.py`)

**The bug**: `_wordnet_category()` only ever checked the topic's FIRST
word. This broke two ways at once:
- Topics starting with an article ("The Dead Sea", "The Statue of
  Liberty") — "The" has no useful WordNet noun sense, so the fallback
  failed immediately, before ever reaching the actual content word.
- Topics where the category-bearing word wasn't first ("Giant's
  Causeway" — "Giant's" resolves to the wrong sense; "Causeway",
  never checked, resolves fine).

Verified against the full 13-video history: **6/13 (46%) were
defaulting to "Amazing Facts"** before the fix.

**The fix**: `_wordnet_category()` now scans every non-stopword word
in the topic, left to right, trying each one's first 5 WordNet noun
senses against `HYPERNYM_CATEGORY_MAP`, returning the first match
found across all words — not just the first word. Also added:
- Stopword list (`the, a, an, of, de, la, le, el, du, von, van, and`)
  so articles/prepositions are skipped rather than tried and failed.
- New keyword coverage: landmarks (`causeway, statue, monument, mahal,
  tower, bridge, fort, wall, dam, lighthouse...`), geological features
  (`sea, lake, salt flat, salar, desert, canyon, geyser, dune...`),
  and elements/chemistry (`neon, element, chemical`).
- New hypernym mappings: `chemical_element.n.01` → Science &
  Technology, `road.n.01` and `sculpture.n.01` → Architecture &
  Structures (catches "Causeway" and "Statue" respectively).
- An explicit `"bermuda triangle"` keyword override (WordNet's
  `triangle` senses resolve to a drafting-instrument sense before the
  constellation sense that would've correctly mapped to Space Facts).

**Verified post-fix, full history**: 0/13 videos fall to the default
category. New spot-checks (Great Wall of China, Eiffel Tower, Roman
Colosseum, Black Hole, Amazon Rainforest, Octopuses) all resolve
correctly.

**Known accepted residual limitation**: single ambiguous words can
still misresolve — e.g. "Chess" hits WordNet's `chess.n.01` (a weedy
plant) before `chess.n.02` (the game), landing in Nature Facts. Not
fixed — genuinely unlikely as a real topic on this channel, and not
worth a new playlist category for one word.

**This fix only affects future videos.** The 6 pre-existing "Amazing
Facts" entries in `videos.json` (Taj Mahal, The Dead Sea, The Statue
of Liberty, Salar de Uyuni, Giant's Causeway, Neon Signs) were NOT
retroactively reclassified — neither in the database nor on YouTube's
actual playlists. A backfill script was offered but not requested/built
yet — flag as available future work if it comes up.

---

## 5. Repo structure — `you-never-knew-automation`

```text
you-never-knew-automation/
├── main.py                       — orchestrator; Stage A0 (analytics) now
│                                    runs first, publisher auth moved up
│                                    from Stage H to support that reuse
├── config.json / config.example.json
├── requirements.txt               — google-api-python-client,
│                                    google-auth-httplib2, google-auth-oauthlib,
│                                    python-dotenv, google-genai, faster-whisper, nltk
├── .env                           — LOCAL ONLY, gitignored
├── credentials.json               — Google OAuth desktop app credential
├── token.json                     — gitignored, restored from GitHub Secret
│                                    YOUTUBE_TOKEN_JSON in CI (fixed this
│                                    session — workflow previously read a
│                                    differently-named, likely-nonexistent
│                                    secret)
├── database/
│   ├── topics.json
│   ├── videos.json                — now includes music_track_id/
│   │                                 music_track_name, published_at,
│   │                                 category, and (once 48h+ old)
│   │                                 performance + performance_captured_at
│   ├── playlists.json             — legacy, unused
│   ├── usage_log.json             — self-tracked API call counts, now
│   │                                 including ElevenLabs/Pexels/Pixabay
│   │                                 with per-video correlation
│   │                                 (a "videos" array of fact_numbers
│   │                                 per service), COMMITTED (not
│   │                                 gitignored) — read live by dashboard
│   └── music_blocklist.json       — permanent Jamendo track exclusion list
├── engines/
│   ├── topic_engine.py
│   ├── numbering.py                — idempotent record_video_state(),
│   │                                  merges by fact_number
│   ├── script_engine.py
│   ├── gemini.py                   — usage_tracker wired in;
│   │                                  get_unique_topic() and
│   │                                  generate_candidate_topic() now
│   │                                  accept performance_context
│   ├── analytics.py                — NEW this session. 48h+ performance
│   │                                  capture, retention-by-category
│   │                                  digest builder
│   ├── elevenlabs.py                — narration; now logs each call to
│   │                                  usage_tracker with fact_number
│   ├── captions.py
│   ├── timeline.py
│   ├── footage.py                  — Pixabay/Pexels calls now logged to
│   │                                  usage_tracker with fact_number
│   │                                  (video_id) threaded through the
│   │                                  whole call chain
│   ├── renderer.py
│   ├── metadata.py                 — REWRITTEN this session, see §4
│   ├── music.py                     — usage_tracker + blocklist wired in
│   ├── notifications.py             — Gmail SMTP failure emails
│   ├── usage_tracker.py             — log_call() now accepts
│   │                                   fact_number, dedupes into a
│   │                                   "videos" list per service
│   └── youtube.py                   — usage_tracker wired in
│                                       (per-operation, quota-weighted);
│                                       SCOPES now includes
│                                       yt-analytics.readonly;
│                                       credentials exposed on the
│                                       instance for analytics.py reuse
├── check_usage.py                  — local dashboard script (console +
│                                      local HTML); same call/video
│                                      correlation + hyperlink fixes as
│                                      the live Netlify dashboard
├── blocklist_track.py              — standalone: blocklist a Jamendo
│                                      track by numeric ID
├── rerun_footage.py                — standalone re-footage/re-render
│                                      (historical, Pangolins)
├── rerun_footage_wombats.py        — same, adapted for Wombats
├── playwright_login.py             — Related Video prototype, SHELVED
├── related_video.py                — Related Video prototype, SHELVED
├── README.md                       — kept in sync this session; see §11
└── .github/workflows/
    └── daily-video.yml             — see §9
```

---

## 5b. Repo structure — `you-never-knew-dashboard` (separate repo)

```text
you-never-knew-dashboard/
├── index.html                     — the live dashboard page; now
│                                     linkifies any raw URL in status
│                                     text and always shows an explicit
│                                     "View full dashboard →" link per
│                                     card; overflow-wrap/word-break CSS
│                                     added as a safety net
├── netlify.toml                   — points functions dir to netlify/functions
└── netlify/
    └── functions/
        └── usage.js               — serverless function, combines live +
                                       self-tracked data; ElevenLabs/
                                       Pexels/Pixabay now get a
                                       supplementary self-tracked
                                       "N calls across M video(s)" note
                                       layered on their live quota %;
                                       ElevenLabs call now trims the key
                                       defensively and, if a call still
                                       fails, surfaces a masked
                                       key preview + length in the error
                                       so a stale/wrong Netlify env var
                                       is visible directly on the card
```

Deployed via Netlify, connected to this repo, auto-deploys on push.
Netlify env vars (**separate credential store from GitHub Secrets** —
set in Netlify's own Site settings → Environment variables, nothing
carries over automatically): `ELEVENLABS_API_KEY`, `PEXELS_API_KEY`,
`PIXABAY_API_KEY`, `GITHUB_REPO=Tobifunmi/you-never-knew-automation`.

`usage.js` fetches `database/usage_log.json` fresh from
`raw.githubusercontent.com/Tobifunmi/you-never-knew-automation/main/...`
on every request — genuinely live on every page reload, no caching, no
rebuild needed. Works because the automation repo is public.

**Resolved incident this session**: ElevenLabs card showed a persistent
HTTP 401 after a key rotation, despite the key testing 200 via direct
curl/PowerShell and the Netlify env var scope being unrestricted (all
contexts). Root cause: an invisible leading/trailing whitespace
character introduced when the key was pasted into Netlify's env var
field — fixed by re-pasting the value cleanly. The defensive `.trim()`
+ masked-key-preview code added during diagnosis stayed in as a
permanent safety net for future rotations.

---

## 6. Bug history — chronological, all fixed/resolved

*(Historical bugs 1–12 from before this session — kept for context,
unchanged from the original master prompt.)*

1. **Fact 174 near-data-loss bug (the original, most important one).**
   Playlist step used to run before `record_video_state()`. A real
   upload succeeded, then the playlist step hit a `playlistNotFound`
   eventual-consistency error, crashing before any database trace was
   saved. **Fixed**: record+complete-topic now runs immediately after
   upload, before playlist logic; playlist step isolated in its own
   try/except.
2. **`HttpError` (and anything else unanticipated) uncaught.** Narrow
   exception tuple broadened to `except Exception`.
3. **Footage failures used `raise SystemExit`**, which isn't an
   `Exception` subclass — skipped the except block entirely. Fixed to
   `raise FootageError`.
4. **Stage A/B sat entirely outside the pipeline's `try` block.** A
   Gemini failure in autonomous mode was completely unhandled. Fixed by
   widening the `try`, guarded by a `topic_reserved` flag.
5. **Wombats (Fact 174 content) footage repetition** — all 5 facts got
   the same clip, pre-`exclude_ids` fix. Re-run locally via standalone
   script, reusing existing narration.
6. **Pangolins (Fact 175) duplicate/bad-footage uploads** — same root
   cause as #5. Approved retest video `wF3mXOU5OOA`; database patched.
7. **Jamendo hard duration requirement caused failures on longer
   narrations.** Fixed: prefers full-length, falls back to longest
   ≥15s + loops via `-stream_loop -1`.
8. **`daily-video.yml`'s cron was claimed fixed but actually wasn't**
   (in an earlier round of work). Verifying the real file showed it
   was still commented out. **Note: as of this session, it has been
   deliberately re-commented-out again by explicit instruction** — see
   §9. Don't treat either the "fixed" or "commented out" state as
   permanent without re-checking the file.
9. **`daily-video.yml`'s commit-back step never included
   `database/usage_log.json`.** Also, `.gitignore` initially excluded
   this file, later reversed once the Netlify dashboard needed it
   committed. Both fixed.
10. **Dashboard repo folder structure wrong on first deploy.**
    `usage.js` was pushed to repo root instead of
    `netlify/functions/usage.js`, and there was no `index.html` at
    root. Fixed by moving the file and renaming.
11. **Statue of Liberty (Fact 180) — real YouTube Content ID claim,
    video blocked globally.** A Jamendo track (marked
    `audiodownload_allowed: true`) matched a registered work in
    Content ID. Discovered fact: CI-produced videos' `work/` directory
    is ephemeral (gone once the job finishes) — only `database/*.json`
    persists, so CI-produced videos can't be locally re-rendered the
    way local-run videos can. **Resolution**: downloaded from YouTube,
    used Adobe Podcast to isolate voice, replaced music, re-uploaded,
    reused original title/description, deleted the claimed video.
    **Structural fix**: `music.py` now records `track_id`/`track_name`
    per video, plus a persistent blocklist + `blocklist_track.py`.
    Fact 180's original track ID was never captured and can't be
    retroactively blocklisted — accepted historical gap.
12. **Jamendo transient failure with a misleading error message.**
    `_query()` only read `results`, ignoring Jamendo's own `headers`
    object (quota/rate-limit failures return HTTP 200 with
    `results: []`, indistinguishable from "genuinely no matches").
    **Fixed**: checks `headers.status`, raises Jamendo's real error.

**New this session:**

13. **Category-guessing defaulted 46% of videos to "Amazing Facts."**
    See §4 for full detail. Root cause: `_wordnet_category()` only
    checked the topic's first word.
14. **YouTube Analytics OAuth scope missing, causing `invalid_scope`
    RefreshError on first Stage A0 run.** The YouTube Analytics API
    wasn't enabled on the Google Cloud project (separate from YouTube
    Data API v3, which was already enabled) — the OAuth consent screen
    accepted the scope, but the API itself rejected tokens carrying
    it. **Fixed**: enabled YouTube Analytics API in Cloud Console,
    deleted stale `token.json`, re-ran `python main.py auth` for a
    genuinely fresh token, updated the (at-the-time-misnamed) GitHub
    secret.
15. **CI secret name mismatch.** `daily-video.yml` restored the token
    from `secrets.TOKEN_JSON`; the actually-created secret (per
    earlier guidance in this same session) was `YOUTUBE_TOKEN_JSON`.
    CI/scheduled runs would have silently gotten no token (or a stale
    one, if `TOKEN_JSON` happened to already exist from before) even
    though the local re-auth was done correctly. **Fixed**: workflow
    now reads `secrets.YOUTUBE_TOKEN_JSON`.
16. **ElevenLabs dashboard card stuck on HTTP 401 after key rotation**
    despite the key itself testing valid. Root cause: invisible
    whitespace from a Netlify UI copy-paste. See §5b for detail and
    the permanent defensive fix left in place.
17. **YouTube Data API dashboard card text overflowing its card
    boundary** (visually broken layout) — the status string embedded
    the same URL a second time ("Authoritative source: https://...")
    that was already rendered as a separate clean hyperlink, with no
    line-wrap handling on the long raw URL. **Fixed**: removed all
    redundant embedded URLs from status text across both the Netlify
    function and `check_usage.py` (6 call sites total); added
    `overflow-wrap: break-word` CSS as a general safety net for any
    other long string in the future.

---

## 7. Known limitations — accepted, not bugs to chase

- **WordNet categorization** — see §4. Fixed for the multi-word-topic
  case that was actually causing 46% of videos to misfile; residual
  single-word sense ambiguity (e.g. "Chess") accepted, not fixed.
- **`footage.py`'s generic fallback** has no relevance check, succeeds
  silently on thin-coverage topics.
- **Jamendo and ElevenLabs free-tier terms are non-commercial-use
  only.** Fine while unmonetized/pre-YPP. Must be revisited together
  (Jamendo license filtering + ElevenLabs plan tier) the moment
  monetization status changes — deliberately deferred. **Separately**,
  the Fact 180 Content ID claim is NOT the same issue — that was an
  actual rights-holder match blocking playback, not a licensing-terms
  violation. Both real, both distinct, same underlying dependency.
- **`gemini.py` validates scripts independently** rather than reusing
  `script_engine.parse_script()` — duplicated contract, not shared.
- **`gemini.py`'s `visual_prompt` output has no explicit
  concrete-noun-first instruction** — worked fine so far, first place
  to check if footage relevance issues start appearing specifically on
  autonomous scripts.
- **`_call_gemini()`'s retry loop catches any exception**, including a
  bad API key, wasting a few seconds of retries on non-transient errors.
- **Narrow residual risk in the Fact 174 fix**: if `record_video_state()`
  itself fails (e.g. disk error) in the brief window right after
  upload, the outer except would still release the topic despite the
  video being live. Accepted.
- **Jamendo's daily/rate quota for the shared `client_id`** is a real,
  hittable limit under heavy local testing. Not something to "fix."
- **Fact 180's original claimed track can never be blocklisted** — its
  ID was never captured. Purely historical gap.
- **The 6 pre-existing "Amazing Facts" videos are not retroactively
  reclassified** by the §4 fix — neither in `videos.json` nor on
  YouTube's actual playlists. A backfill script is easy to write if
  wanted but hasn't been requested.
- **The 48h analytics performance snapshot is captured once, not
  continuously refreshed.** Reflects cumulative stats at the moment a
  video first crossed 48h old; later views don't update it. Deliberate
  "how did it land" snapshot, not a live number. The performance
  digest fed to Gemini stays empty (no prompt change at all) until ≥3
  videos have a captured snapshot.
- **`published_at` is an approximation** (captured via
  `datetime.now(timezone.utc)` immediately after the upload call
  returns), not YouTube's own reported publish timestamp. Accurate to
  within a few seconds; not pulled from the API response.

---

## 8. Deliberately deferred work

**Shorts "Related Video" (End Screen).** No public API for Studio's End
Screen setting. Decision made: always link to the immediately-previous
fact's video. Mechanism undecided — a Playwright/Studio browser-
automation prototype exists (`playwright_login.py`, `related_video.py`,
`test_related_video.py`) but was explicitly shelved before a working
headed run was completed. Simpler alternative not yet built: a link in
the video description instead. Do not resume without explicit direction.

**Zack D Films-style production skill.** Explored via Higgsfield MCP
for a separate, more elaborate 3D-animated short-form pipeline; stalled
at a Higgsfield billing barrier. Not connected to the You Never Knew
pipeline described in this document — separate effort, separate status.

---

## 9. Credentials / environment variables / GitHub Secrets

**Automation repo** — local `.env` + GitHub Secrets (same names,
restored at the start of each Actions run): `GEMINI_API_KEY` (model:
`GEMINI_MODEL` env var, defaults to `gemini-3.6-flash`, free tier),
`ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` ("Adam," free/stock
voice), `PEXELS_API_KEY`, `PIXABAY_API_KEY`, `JAMENDO_CLIENT_ID`,
`GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` (2-Step Verification required;
SMTP-based, not Gmail API/OAuth — deliberate, smaller credential
surface). YouTube OAuth: `credentials.json` (never committed) +
`token.json` restored in CI from the **`YOUTUBE_TOKEN_JSON`** GitHub
Secret (name fixed this session — see §6 item 15).
`authenticate(interactive=not production)` fails loudly rather than
hanging on a headless CI re-auth need.

**IMPORTANT — token scope**: `token.json` must carry BOTH the YouTube
upload scope AND `yt-analytics.readonly` (added this session). If
Stage A0 ever throws `invalid_scope`/`RefreshError` again, the two
things to check in order are (1) is the YouTube Analytics API enabled
in the Google Cloud project, separate from YouTube Data API v3, and
(2) was the token actually re-minted (`python main.py auth`, after
deleting the stale one) since that scope was added.

**Dashboard repo (Netlify)** — separate store, Site settings →
Environment variables: `ELEVENLABS_API_KEY`, `PEXELS_API_KEY`,
`PIXABAY_API_KEY`, `GITHUB_REPO=Tobifunmi/you-never-knew-automation`.
Nothing here carries over from GitHub Secrets automatically. When
rotating any of these three keys, paste carefully — a copy-paste
whitespace issue caused a real, hard-to-diagnose 401 this session (see
§6 item 16).

---

## 10. `daily-video.yml` — current real state (verified, not assumed)

```yaml
on:
  #schedule:
  #- cron: '0 10 * * 1,4'

  # Manual trigger button in GitHub Actions UI
  workflow_dispatch:
```

**The cron is deliberately commented out as of this session, by
explicit instruction** — do not re-enable without being asked. Only
the manual `workflow_dispatch` button in the Actions UI currently
triggers a run.

Steps, in order: checkout → setup Python 3.11 → install ffmpeg →
install pip deps → download WordNet corpus → restore
`topics.json`/`videos.json`/`token.json` from Secrets (only if not
already present for the first two — bootstrap fallback; token.json is
always restored if the secret is set) → run `python main.py run
--production` with all secrets injected as env vars → commit-back step
(`if: always()`, so it commits state even after a pipeline failure) —
`git add database/topics.json database/videos.json
database/usage_log.json`, commit, push, all with `|| true`.

---

## 11. Documentation state

`README.md` in the automation repo was rewritten this session to match
everything above — current status table, a new "Analytics feedback
loop" section, a new "API usage dashboard" section, an updated project
structure tree including `analytics.py`/`usage_tracker.py`, and the
known-limitations section corrected (the old "Taj Mahal falls through
to Amazing Facts" limitation replaced with the fixed/verified state).
Treat the README as reliably current as of this session — if it drifts
from this document in a future conversation, the more recently-edited
one wins; verify against the actual repo file rather than assuming
either is right.

---

## 12. Working style / operating principles

Each of these has concretely prevented or caught a real problem in
this project's actual history — not arbitrary rules:

- **Verify against actual files/logs before treating something as
  done.** The cron "was pushed" claim turned out false on inspection
  once already; the CI secret-name mismatch this session is the same
  lesson recurring — an instruction was given, confirmed by the user
  as done, and still turned out to reference the wrong secret name
  until the actual workflow file was read.
- **No manual overrides for anything unattended.** Fixes are either
  genuinely automated or explicitly flagged as needing a one-time
  human step (Playwright login, generating a Gmail App Password, a
  fresh OAuth re-auth for a new scope) — never a silent assumption
  someone will intervene during a scheduled run.
- **Prefer free/offline over paid/AI where genuinely sufficient**
  (WordNet over an AI classifier; SMTP App Password over Gmail
  API/OAuth; self-tracked call counters over paid monitoring) —
  judgment call each time, not dogma.
- **Standalone, single-purpose `.py` files** for one-off/manual-debug
  operations rather than folding one-off logic into the main pipeline.
- **Isolate failure domains.** A failure in one stage should never
  retroactively invalidate work that already genuinely succeeded.
  Analytics.py follows this too — every function swallows its own
  errors so a broken Analytics scope degrades to "no context this
  run," never a pipeline failure.
- **Accept known, narrow, low-probability limitations rather than
  over-engineering fixes** — but always name them explicitly rather
  than leaving them undocumented (§7 is the running list).
- **When infrastructure changes what's true, go back and fix the
  earlier advice that's now wrong** — the `.gitignore` reversal on
  `usage_log.json` is the original example; this session's secret-name
  fix and README update are the same principle applied again.
- **Patches, not direct pushes, from this assistant.** This assistant
  does not have push credentials to either repo — all code changes are
  delivered as `git format-patch` files, applied locally via `git am
  <file>.patch` then `git push origin main` by the user. Expect this
  pattern to continue in future sessions unless that changes.
