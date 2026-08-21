# MASTER CONTINUATION PROMPT — "You Never Knew" Automated YouTube Shorts Factory

Use this as full context in a new conversation. Reflects the actual
verified state of the project, not any original starter plan — several
things below were only discovered to be wrong (not just undone) by
reading real files, so treat this as ground truth over any older summary.

GitHub username: **tobifunmi**. Automation repo:
`github.com/tobifunmi/you-never-knew-automation` (public). Dashboard repo:
`github.com/tobifunmi/you-never-knew-dashboard` (public). Live dashboard:
`https://you-never-knew.netlify.app/`.

---

## 1. What this project is

A fully automated production and publishing pipeline for the YouTube
channel **You Never Knew** — "5 Facts You Didn't Know About [Topic]"
YouTube Shorts. Topic selection, script writing, narration, footage,
captions, rendering, background music, metadata, YouTube upload, playlist
assignment, database recording, and failure notification all run on
GitHub Actions. Runs locally on Windows 10/11 (PowerShell,
`C:\Users\user\Documents\You Never Knew`) for development/testing.

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
| Full unattended automation (GitHub Actions) | ✅ Done — cron **genuinely** enabled now: `0 10 * * 1,4` (previously claimed-but-not-actually-live, see §5) |
| Email failure notifications (Gmail SMTP) | ✅ Done, tested, confirmed firing correctly on a real transient failure |
| Playlist/record ordering bug | ✅ Fixed |
| API usage dashboard (local script) | ✅ Done — `check_usage.py` |
| API usage dashboard (public, live, Netlify-hosted) | ✅ Done — `you-never-knew.netlify.app` |
| Per-video Jamendo track ID/name recording | ✅ Done |
| Persistent Jamendo track blocklist | ✅ Done, built but not yet populated (see §6) |
| Wombats (Fact 174) footage repetition | ✅ Fixed |
| Pangolins (Fact 175) bad-footage database record | ✅ Fixed |
| Statue of Liberty (Fact 180) Content ID claim | ✅ Resolved manually (see §5, item 11) |
| Shorts "Related video" End Screen | 🔜 Deliberately deferred |

---

## 3. Pipeline stages, actual execution order (`main.py` `run_pipeline()`)

0. **Config load** — `config.json`.
1. **Stage A/B — Topic + script ingestion.** Manual (`script_path` given,
   `script_engine.parse_script()`, duplicate check aborts via
   `SystemExit`) or autonomous (`gemini.get_unique_topic()` +
   `gemini.generate_script()`). `numbering.get_next_fact_number()`
   assigns the fact number. `topic_engine.reserve_topic()` (reservation,
   not completion). This entire stage is now inside the pipeline's `try`
   block (previously wasn't — see §5).
2. **Stage C — Narration** (ElevenLabs, `engines/elevenlabs.py`).
3. **Transcription** — local Whisper, free regardless of narration source.
4. **Timeline** — `timeline.build_segment_timeline()`, word-count
   alignment between script and Whisper output.
5. **Stage D — Footage** (`engines/footage.py`). Pixabay specific →
   Pexels specific → Pixabay broad topic fallback → Pexels broad topic
   fallback → generic "nature landscape"/"scenery" (no relevance check,
   last resort). `exclude_ids` enforces variety across the 5 facts within
   one video.
6. **Stage E — Captions file** (ASS).
7. **Stage F — Render.** `normalize_all_segments()` →
   `concatenate_segments()` → background music fetch/mix →
   `burn_in_captions()`.
   - Music: `music.fetch_and_download_background_track()` now returns a
     **dict** (`path`, `track_id` namespaced as `"jamendo:<id>"`,
     `track_name`, `track_url`), not a bare path string. Prefers a track
     ≥ narration length; falls back to the longest track ≥ 15s
     (`MIN_LOOPABLE_DURATION`) and loops it via ffmpeg `-stream_loop -1`
     in `mix_background_music()`. Filters out anything in the persistent
     blocklist (`database/music_blocklist.json`) before selection.
     `_query()` now checks Jamendo's own `headers.status` field and
     raises a specific error with Jamendo's real error message if the API
     call itself failed (quota/rate-limit/etc.) — previously this was
     silently indistinguishable from "no tracks match," which caused a
     real, confusing failure (see §5, item 12).
8. **Stage G — Metadata.** Title/description/tags, WordNet-based playlist
   categorization (offline, free).
9. **Stage H — Upload.** `unlisted` unless `--production`.
10. **Record + complete topic.** Runs **immediately after upload
    succeeds, before the playlist step** (deliberate, load-bearing
    ordering — see §5). Now also records `music_track_id` and
    `music_track_name` alongside the existing fields.
11. **Stage I — Playlist.** Isolated `try/except`. Success →
    `record_video_state()` called again (safe, merges by `fact_number`)
    with real `playlist_id` and `state="playlist_added"`. Failure → sends
    a failure email, prints a warning, does **not** re-raise — video is
    already safely recorded, so this is never treated as a pipeline
    failure.
12. **Failure path** (any stage): outer `except Exception` (broadened
    from a narrow tuple, now also catches `HttpError` and anything
    unanticipated). Sends a detailed failure email via
    `engines/notifications.py` (Gmail SMTP, App Password auth) with
    current stage, error, fact/topic if known, mode, full traceback. Then
    releases the topic reservation **only if it was actually reserved**
    (`topic_reserved` flag). Confirmed working in production on a real
    transient Jamendo failure — email arrived, topic was released, retry
    succeeded cleanly.

---

## 4. Repo structure — `you-never-knew-automation`

```text
you-never-knew-automation/
├── main.py
├── config.json / config.example.json
├── requirements.txt
├── .env                        — LOCAL ONLY, gitignored
├── credentials.json             — Google OAuth desktop app credential
├── token.json                   — gitignored, restored from GitHub Secret in CI
├── database/
│   ├── topics.json
│   ├── videos.json              — now includes music_track_id/music_track_name per record
│   ├── playlists.json           — legacy, unused
│   ├── usage_log.json           — self-tracked API call counts (Jamendo/Gemini/YouTube),
│   │                               COMMITTED (not gitignored) — read live by the Netlify dashboard
│   └── music_blocklist.json     — permanent Jamendo track exclusion list
├── engines/
│   ├── topic_engine.py
│   ├── numbering.py              — idempotent record_video_state(), merges by fact_number
│   ├── script_engine.py
│   ├── gemini.py                 — usage_tracker wired in
│   ├── elevenlabs.py
│   ├── captions.py
│   ├── timeline.py
│   ├── footage.py
│   ├── renderer.py
│   ├── metadata.py
│   ├── music.py                  — usage_tracker + blocklist wired in
│   ├── notifications.py          — Gmail SMTP failure emails
│   ├── usage_tracker.py          — shared local call-counter, writes database/usage_log.json
│   └── youtube.py                — usage_tracker wired in (per-operation, quota-weighted)
├── check_usage.py                — local dashboard script (console + local HTML)
├── blocklist_track.py            — standalone: blocklist a Jamendo track by numeric ID
├── rerun_footage.py              — standalone re-footage/re-render (Pangolins)
├── rerun_footage_wombats.py      — same, adapted for Wombats
├── playwright_login.py           — Related Video prototype, SHELVED, not wired in
├── related_video.py              — Related Video prototype, SHELVED, not wired in
└── .github/workflows/
    └── daily-video.yml           — see §9, cron now genuinely active
```

## 4b. Repo structure — `you-never-knew-dashboard` (separate repo)

```text
you-never-knew-dashboard/
├── index.html                    — the live dashboard page (was usage-dashboard.html, renamed)
├── netlify.toml                  — points functions dir to netlify/functions
└── netlify/
    └── functions/
        └── usage.js              — serverless function, combines live + self-tracked data
```

Deployed via Netlify, connected to this repo, auto-deploys on push.
Netlify env vars (separate credential store from GitHub Secrets — set in
Netlify's own Site settings, nothing carries over automatically):
`ELEVENLABS_API_KEY`, `PEXELS_API_KEY`, `PIXABAY_API_KEY`,
`GITHUB_REPO=tobifunmi/you-never-knew-automation`.

`usage.js` fetches `database/usage_log.json` fresh from
`raw.githubusercontent.com/tobifunmi/you-never-knew-automation/main/...`
on every request — genuinely live on every page reload, no caching, no
rebuild needed. Works because the automation repo is public.

---

## 5. Bug history — chronological, all fixed/resolved

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
   script, reusing existing narration (no new ElevenLabs cost). Approved,
   re-uploaded manually.
6. **Pangolins (Fact 175) duplicate/bad-footage uploads** — same root
   cause as #5. Approved retest video `wF3mXOU5OOA`; database patched via
   standalone `fix_pangolins_record.py`; other upload deleted directly on
   YouTube.
7. **Jamendo hard duration requirement caused failures on longer
   narrations.** Fixed: prefers full-length, falls back to longest ≥15s +
   loops via `-stream_loop -1`.
8. **`daily-video.yml`'s cron was claimed fixed but actually wasn't.**
   Verifying the real file showed `schedule:`/`- cron:` were STILL
   commented out — only `workflow_dispatch` (manual) was ever actually
   live. This is a genuine example of "confirmed" state drifting from
   reality; caught only by reading the actual file, not by trusting the
   earlier confirmation. **Fixed**, properly uncommented and indented
   this time, confirmed via the file itself.
9. **`daily-video.yml`'s commit-back step never included
   `database/usage_log.json`.** Also, `.gitignore` initially had this
   file excluded (earlier advice, later reversed once the Netlify
   dashboard needed it committed, not ignored). Both fixed.
10. **Dashboard repo folder structure wrong on first deploy.**
    `usage.js` was pushed to repo root instead of
    `netlify/functions/usage.js` (Netlify silently doesn't register it as
    a function outside that exact path), and there was no `index.html`
    at root (only `usage-dashboard.html`), causing a 404 on the bare
    domain. Fixed by moving the file and renaming.
11. **Statue of Liberty (Fact 180) — real YouTube Content ID claim,
    video blocked globally.** A Jamendo track (marked
    `audiodownload_allowed: true`) matched a registered "Epic Cinematic
    Trailer" work in Content ID — Jamendo's free-download flag doesn't
    guarantee a track is clean against YouTube's Content ID database.
    **Important discovered fact**: this video was produced by a GitHub
    Actions CI run, and CI runners are ephemeral — the entire
    `work/Fact_180_.../` directory (narration, footage, everything) only
    ever existed on that one job's runner and was gone permanently once
    the job finished. Only `database/*.json` persists across runs (via
    commit-back). This means **CI-produced videos cannot be locally
    re-rendered** the way Wombats/Pangolins were (those were local runs,
    so `work/` persisted on the Windows machine) — only Studio-side fixes
    (mute/replace, works server-side on the uploaded asset) or a full
    fresh regeneration are possible for CI-produced videos.
    **Actual resolution taken**: downloaded the video from YouTube, used
    Adobe Podcast to separate voice from music, replaced the music,
    re-exported, re-uploaded, reused the original Fact 180
    title/description, deleted the original claimed video.
    **Structural fix applied**: `music.py` now records `track_id`/
    `track_name` per video in `videos.json` going forward, plus a
    persistent `database/music_blocklist.json` + `add_to_blocklist()` +
    standalone `blocklist_track.py` so any future claimed track can be
    permanently excluded once identified. **The Fact 180 track's own ID
    was never captured** (tracking didn't exist yet at the time) and
    can't be recovered retroactively — the blocklist starts empty, this
    is accepted, not a bug.
12. **Jamendo transient failure with a misleading error message.**
    A run failed with "No Jamendo track >= 15.0s found" for both the
    topic tags AND the generic "cinematic" fallback simultaneously —
    implausible as a genuine empty-catalog result. Root cause:
    `_query()` only read the `results` field and completely ignored
    Jamendo's own `headers` object (which reports call-level success/
    failure — quota exhaustion, rate limiting, bad params all return
    HTTP 200 with `results: []`, indistinguishable from "genuinely no
    matches" under the old code). **Fixed**: `_query()` now checks
    `headers.status` and raises a specific error surfacing Jamendo's
    real error message. The failure notification + topic-release safety
    net worked correctly throughout this incident regardless — email
    sent, topic released, retry on the same topic succeeded cleanly
    (Fact 183, "Giant's Causeway," confirmed end-to-end including the
    new `music_track_id`/`music_track_name` fields in `videos.json`).

---

## 6. Known limitations — accepted, not bugs to chase

- **WordNet categorization** misclassifies proper-noun topics — confirmed
  on both "Taj Mahal" and "Giant's Causeway," both fell through to
  generic "Amazing Facts." Occasional one-off `CATEGORY_KEYWORDS`
  additions are acceptable maintenance; AI classification and manual
  correction both explicitly rejected.
- **`footage.py`'s generic fallback** has no relevance check, succeeds
  silently on thin-coverage topics.
- **Jamendo and ElevenLabs free-tier terms are non-commercial-use only.**
  Fine while unmonetized/pre-YPP. Must be revisited together (Jamendo
  license filtering + ElevenLabs plan tier) the moment monetization
  status changes — deliberately deferred. **Separately**, the Content ID
  claim issue (§5, item 11) is NOT the same thing as this licensing note
  — that's about usage rights, the claim was about an actual
  rights-holder match blocking playback. Both are real but distinct
  risks with this same underlying dependency.
- **`gemini.py` validates scripts independently** rather than reusing
  `script_engine.parse_script()` — duplicated contract, not shared.
- **`gemini.py`'s `visual_prompt` output has no explicit
  concrete-noun-first instruction** — worked fine so far, first place to
  check if footage relevance issues start appearing specifically on
  autonomous (not hand-written) scripts.
- **`_call_gemini()`'s retry loop catches any exception**, including a
  bad API key, wasting a few seconds of retries on non-transient errors.
- **Narrow residual risk in the Fact 174 fix**: if `record_video_state()`
  itself fails (e.g. disk error) in the brief window right after upload,
  the outer except would still release the topic despite the video being
  live. Meaningfully narrower than the original bug; accepted.
- **Jamendo's daily/rate quota for the shared `client_id` is a real,
  hittable limit** given how much local testing happens in short bursts —
  confirmed as the likely (though not 100% certain) cause of one real
  failure. Not something to "fix," just something to expect occasionally
  during heavy testing days.
- **Fact 180's original claimed track can never be blocklisted** — its ID
  was never captured. Purely historical gap, doesn't affect any other
  video.

---

## 7. Deliberately deferred work

**Shorts "Related Video" (End Screen).** No public API for Studio's End
Screen setting. Decision made: always link to the immediately-previous
fact's video. Mechanism undecided — a Playwright/Studio browser-
automation prototype exists (`playwright_login.py`, `related_video.py`,
`test_related_video.py`) but was explicitly shelved before a working
headed run was completed ("I'm not doing the playwright thing again").
Simpler alternative not yet built: a link in the video description
instead. Do not resume without explicit direction.

---

## 8. Credentials / environment variables / GitHub Secrets

**Automation repo** — local `.env` + GitHub Secrets (same names, restored
at the start of each Actions run):
`GEMINI_API_KEY` (model: `GEMINI_MODEL` env var, defaults to
`gemini-3.6-flash`, free tier), `ELEVENLABS_API_KEY`,
`ELEVENLABS_VOICE_ID` ("Adam," free/stock voice), `PEXELS_API_KEY`,
`PIXABAY_API_KEY` (confirmed present in both Secrets and the workflow
YAML), `JAMENDO_CLIENT_ID`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`
(requires 2-Step Verification on the Google account; SMTP-based, not
Gmail API/OAuth — smaller credential surface, deliberate choice).
YouTube OAuth: `credentials.json` + `token.json`
(`authenticate(interactive=not production)` fails loudly rather than
hanging on a headless CI re-auth need).

**Dashboard repo (Netlify)** — separate store, Site settings →
Environment variables: `ELEVENLABS_API_KEY`, `PEXELS_API_KEY`,
`PIXABAY_API_KEY`, `GITHUB_REPO=tobifunmi/you-never-knew-automation`.
Nothing here carries over from GitHub Secrets automatically.

---

## 9. `daily-video.yml` — current real state (verified, not assumed)

```yaml
on:
  schedule:
    - cron: '0 10 * * 1,4'
  workflow_dispatch:
```

Steps, in order: checkout → setup Python 3.11 → install ffmpeg → install
pip deps → download WordNet corpus → restore `topics.json`/`videos.json`/
`token.json` from Secrets (only if not already present — bootstrap
fallback, not the primary persistence mechanism) → run
`python main.py run --production` with all secrets injected as env vars →
commit-back step (`if: always()`, so it commits state even after a
pipeline failure) — `git add database/topics.json database/videos.json
database/usage_log.json`, commit, push, all with `|| true` so a failed
git operation doesn't fail the whole job.

---

## 10. Working style / operating principles

Each of these has concretely prevented or caught a real problem in this
project's actual history — not arbitrary rules:

- **Verify against actual files/logs before treating something as done.**
  The cron "was pushed" claim (item 8, §5) turned out false on
  inspection — this is the clearest example in the whole project of why
  this rule exists.
- **No manual overrides for anything unattended.** Fixes are either
  genuinely automated or explicitly flagged as needing a one-time human
  step (Playwright login, generating a Gmail App Password) — never a
  silent assumption someone will intervene during a scheduled run.
- **Prefer free/offline over paid/AI where genuinely sufficient**
  (WordNet over an AI classifier; SMTP App Password over Gmail
  API/OAuth) — judgment call each time, not dogma.
- **Standalone, single-purpose `.py` files** for one-off/manual-debug
  operations (`rerun_footage.py`, `fix_pangolins_record.py`,
  `blocklist_track.py`, `test_related_video.py`) rather than folding
  one-off logic into the main pipeline.
- **Isolate failure domains.** A failure in one stage should never
  retroactively invalidate work that already genuinely succeeded — the
  throughline connecting the Fact 174 fix, playlist isolation, and the
  `topic_reserved` guard.
- **Accept known, narrow, low-probability limitations rather than
  over-engineering fixes** — but always name them explicitly (WordNet
  proper-noun edge cases, the residual disk-write-failure race, Fact
  180's unrecoverable track ID) rather than leaving them undocumented.
- **When infrastructure changes what's true, go back and fix the earlier
  advice that's now wrong** — the `.gitignore` reversal on
  `usage_log.json` is the clearest example: correct advice in isolation,
  wrong once the Netlify dashboard needed that file committed, corrected
  explicitly rather than left as silent drift.
