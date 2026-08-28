# MASTER CONTINUATION PROMPT — "You Never Knew" Automated YouTube Shorts Factory

Use this as full context in a new conversation. Reflects the actual
verified state of the project as of **28 Aug 2026** — several things
below were only discovered to be wrong (not just undone) by reading
real files/logs directly, so treat this as ground truth over any older
summary, including any earlier version of this same document (an older
version is committed at `MASTER_CONTINUATION_PROMPT.md` in the
automation repo itself — this document supersedes it; consider
re-committing this version over it).

GitHub username: **Tobifunmi** (capitalized — the automation repo's
remote previously pointed at the old lowercase `tobifunmi` URL and
GitHub silently redirected; worth confirming both repos' remotes use
the current casing rather than relying on a redirect indefinitely).
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

**16 videos produced so far** (`database/videos.json`, fact numbers
173–188), all currently `unlisted` (test/dev mode — the channel has not
gone to production/public posting yet).

---

## 2. Current status

| Stage | Status |
|---|---|
| YouTube publisher (OAuth, upload, playlists, DB recording) | ✅ Done |
| **Narration — Kokoro-82M** (local/offline, no API key, no char cap) | ✅ Done — swapped from ElevenLabs; see §4 |
| Footage (Pixabay → Pexels waterfall) | ✅ Done |
| Captions (local Whisper, burned-in ASS) | ✅ Done |
| Render (FFmpeg, 1080×1920) | ✅ Done |
| Background music (Jamendo, loops short tracks, blocklist-aware) | ✅ Done |
| Topic engine + fact numbering | ✅ Done |
| Autonomous topic/script generation (Gemini) | ✅ Done, audited |
| 48h YouTube Analytics feedback loop (Stage A0, feeds topic selection) | ✅ Done — see §5 for a real, verified nuance in how it behaves on zero-view unlisted videos |
| Category-guessing fix (WordNet: scans every word, not just the first) | ✅ Done — verified 0/13 fall to default (was 6/13) |
| API usage dashboard: live quotas, call/video correlation, hyperlinks | ✅ Done |
| **Pexels dashboard caching bug** (quota looked frozen despite real usage climbing) | ✅ Fixed — see §6 item 18 |
| **Dashboard: ElevenLabs card replaced with Kokoro card** | ✅ Done — see §4 |
| Full unattended automation (GitHub Actions) | ⚠️ Cron set to **daily**, deliberately left commented out — `workflow_dispatch` (manual button) only, until the unpublished-video backlog clears. This is an explicit, repeated choice, not an oversight. |
| Email failure notifications (Gmail SMTP) | ✅ Done, tested, confirmed firing correctly on a real transient failure |
| Playlist/record ordering bug | ✅ Fixed (historical) |
| CI secret name mismatch (`TOKEN_JSON` vs `YOUTUBE_TOKEN_JSON`) | ✅ Fixed |
| Persistent Jamendo track blocklist | ✅ Done, built and in active use |
| Shorts "Related video" End Screen | 🔜 Deliberately deferred |
| Google AI Plus/Pro student offer | ℹ️ Researched, concluded **not needed** — see §8b |

---

## 3. Pipeline stages, actual execution order (`main.py` `run_pipeline()`)

0. **Config load** — `config.json`. Key fields: `starting_fact_number:
   172`, `title_template: "Fact {fact_number}: 5 Facts You Didn't Know
   About {topic}"`, `youtube.privacy_status: "unlisted"`,
   `youtube.category_id: "27"` (Education), `youtube.auto_create_playlists:
   true`.
1. **Stage A0 — 48h+ performance capture.** `engines/analytics.py ::
   update_performance_log(publisher)` runs FIRST, before topic
   selection. Scans `database/videos.json` for any video with a
   `youtube_id` + `published_at` that's ≥48h old and has no
   `performance` block yet, pulls cumulative
   views/likes/comments/averageViewPercentage/estimatedMinutesWatched
   via the **YouTube Analytics API**, writes it back into that video's
   record. Walks the WHOLE list each run. Once ≥3 videos have captured
   performance, `build_performance_context()` produces a
   retention-by-category digest fed into the next step. Never raises.
   Requires the `yt-analytics.readonly` OAuth scope. `YouTubePublisher`
   is instantiated and authenticated at this early point specifically
   so this step can reuse the same OAuth session.
   **Verified real-world nuance (28 Aug)**: a video with genuinely zero
   real views (unlisted, never watched by anyone but the uploader) gets
   `rows: []` back from the Analytics API. The code treats this the
   same as "not eligible yet" — `performance` stays `None`, and the
   video gets silently re-attempted on every subsequent run,
   indefinitely, harmlessly. This is NOT a bug — it's why fact 185
   (Neon Signs, 1 self-view) got a captured snapshot while fact 186
   (Machu Picchu, same age bracket, apparently 0 views) still shows
   `performance: None` after multiple later runs. Practical
   consequence: while the channel stays in unlisted/no-real-audience
   test mode, most videos may never accumulate a captured snapshot,
   which also delays the ≥3-videos threshold for the Gemini performance
   digest ever activating. This should resolve naturally once videos
   go public and get real views.
2. **Stage A/B — Topic + script ingestion.** Manual or autonomous
   (`gemini.get_unique_topic(performance_context=...)` +
   `gemini.generate_script()`). `numbering.get_next_fact_number()`
   assigns the fact number. `topic_engine.reserve_topic()`.
3. **Stage C — Narration.** `engines/kokoro.py :: generate_narration()`
   — see §4 for full detail. Local/offline, no API key.
4. **Transcription** — local Whisper, free regardless of narration
   source.
5. **Timeline** — `timeline.build_segment_timeline()`.
6. **Stage D — Footage.** Pixabay specific → Pexels specific → Pixabay
   broad topic fallback → Pexels broad topic fallback → generic
   "nature landscape"/"scenery" (no relevance check, last resort).
   Every Pexels/Pixabay search call is logged via
   `usage_tracker.log_call(..., fact_number=video_id)`.
7. **Stage E — Captions file** (ASS).
8. **Stage F — Render.** Normalize → concatenate → background music
   fetch/mix → burn in captions.
9. **Stage G — Metadata.** Title/description/tags, WordNet-based
   playlist categorization — see §7 for the full rewrite detail.
10. **Stage H — Upload.** `unlisted` unless `--production`.
    `published_at` captured immediately after upload
    (`datetime.now(timezone.utc)`, approximated).
11. **Record + complete topic.** Runs immediately after upload
    succeeds, before the playlist step (deliberate, load-bearing
    ordering — see §6 item 1).
12. **Stage I — Playlist.** Isolated `try/except`, never re-raises —
    video is already safely recorded regardless of playlist outcome.
13. **Failure path**: outer `except Exception`. Sends a detailed
    failure email (Gmail SMTP). Releases topic reservation only if it
    was actually reserved.

---

## 4. Narration engine swap: ElevenLabs → Kokoro-82M (this session)

**Motivation, with real numbers.** ElevenLabs' free tier is 10,000
characters/month. Actual narration length observed: ~1,676 chars/video.
That's ~6 videos/month max — already tight at the prior 2x/week cadence
(~8-9/month) and a hard blocker for daily posting (~30/month needs
~50,000 chars/month, 5x over free tier). Kokoro-82M
(github.com/hexgrad/kokoro) is Apache-2.0-licensed, runs entirely
locally on CPU, no API key, no character limit. Its permissive license
also independently closes a licensing gap: ElevenLabs' free tier is
non-commercial-use only, which would've needed revisiting the moment
the channel monetizes — with Kokoro that's now moot for narration.

**Interface preserved on purpose.** `engines/kokoro.py::generate_narration(script,
output_path) -> dict` matches `elevenlabs.py`'s exact signature and
return shape (`NarrationError` too), so nothing downstream changed
except `main.py`'s narration file extension (`.mp3` → `.wav` — Kokoro
outputs WAV natively via `soundfile`, no reason to add an unnecessary
transcode step).

**Real API confirmed by reading the actual installed package** (not
assumed from memory): `KPipeline(lang_code='a')`, called as
`pipeline(text, voice=..., speed=..., split_pattern='\n+')`, yields a
generator of `Result` objects with `.graphemes`/`.phonemes`/`.audio`
(a `torch.FloatTensor`, converted to numpy before concatenation).
Default `split_pattern` is `r'\n+'`, so `build_narration_text()`
deliberately joins hook/fact-narrations/ending with `\n\n` (not
spaces) — chunks generation naturally at those boundaries rather than
sending one long unbroken block through the model. A small
(~250ms, `KOKORO_PAUSE_SECONDS`-configurable) silence gap is inserted
between concatenated chunks so the stitching doesn't sound abrupt.

**Voice**: defaults to `"am_adam"` (American English male — picked by
name-coincidence with the ElevenLabs "Adam" voice this replaces, not a
rigorous audition), overridable via `KOKORO_VOICE_ID` env var.
`KOKORO_SPEED` also configurable, defaults to `1.0`.

**Setup requirements** (real, not automatic):
- `espeak-ng` **system package** (not pip-installable). Windows: `.msi`
  from the espeak-ng GitHub releases page. CI: `apt-get install
  espeak-ng`, added to `daily-video.yml` alongside the existing
  `ffmpeg` install.
- Python 3.9–3.12 specifically for Kokoro (the repo's CI already uses
  3.11, compatible).
- First run downloads ~327MB of model weights from Hugging Face —
  needs real internet access the first time only; cached afterward at
  `~/.cache/huggingface`. CI caches this directory across runs via
  `actions/cache`, keyed on `hashFiles('requirements.txt')`.

**What was and wasn't verified in the assistant's sandbox** (important
— be precise about this in any follow-up): the sandbox used to build
this had `pypi.org` access (so `pip install kokoro soundfile` and
`apt-get install espeak-ng` both succeeded) but NOT `huggingface.co`
access. So: imports were confirmed clean, no naming collision between
`engines/kokoro.py` and the pip `kokoro` package was confirmed
empirically, integration with `script_engine`'s script dict shape was
confirmed, and the error-wrapping path was confirmed (failed at
exactly the expected point — the Hugging Face model download — wrapped
correctly as `NarrationError`). **Actual audio generation and voice
quality were NOT verified in that sandbox** — that could only happen
on a machine with real Hugging Face access.

**Real-world result, confirmed by the user**: ran successfully on the
first real local attempt (`python main.py run`, no `--production`),
completed the full pipeline including a successful `unlisted` upload,
and the user's direct assessment of the narration was **"it sounded
the same."**

**`elevenlabs.py` was NOT deleted** — kept as a one-import/one-filename
rollback path (`main.py` line ~16 and the narration output path) if
Kokoro's quality doesn't hold up at scale. It's also no longer checked
by either usage dashboard (see below).

**Dashboard follow-up**: the ElevenLabs live-quota card was replaced
with a Kokoro card in both `check_usage.py` (local) and
`netlify/functions/usage.js` + `index.html` (live). Kokoro has no
external API/account, so this isn't a live quota check — it just
reads a self-tracked "N videos narrated" count from
`usage_log.json["kokoro"]`, added via a
`usage_tracker.log_call("kokoro", fact_number=...)` call at the end of
`generate_narration()` (success-only — unlike the paid engines it
replaced, there's no credit spent on a failed local run, so this is
purely a production counter, not a quota-consumption counter).
**Verified timing gotcha, worth knowing**: the very first real Kokoro
run (which produced fact 187 or 188, per git history — see §5)
happened BEFORE this dashboard-tracking code existed. So even though
Kokoro narration genuinely already ran successfully once (per the
user's own confirmation), the dashboard's Kokoro card will still show
"No videos narrated yet" until the NEXT run after that patch was
applied — not a bug, just sequencing.

---

## 5. Repo structure — `you-never-knew-automation`

```text
you-never-knew-automation/
├── main.py                       — orchestrator; Stage A0 (analytics) runs
│                                    first; imports engines.kokoro (not
│                                    engines.elevenlabs) for narration
├── config.json / config.example.json
├── requirements.txt               — google-api-python-client,
│                                    google-auth-httplib2, google-auth-oauthlib,
│                                    python-dotenv, google-genai, faster-whisper,
│                                    nltk, kokoro>=0.9.4, soundfile, numpy
├── MASTER_CONTINUATION_PROMPT.md  — an earlier version of this exact document,
│                                    committed into the repo by the user;
│                                    THIS document (from this session) is more
│                                    current — consider re-committing it over
│                                    the checked-in one
├── .env                           — LOCAL ONLY, gitignored
├── credentials.json               — Google OAuth desktop app credential
├── token.json                     — gitignored, restored from GitHub Secret
│                                    YOUTUBE_TOKEN_JSON in CI
├── database/
│   ├── topics.json
│   ├── videos.json                — 16 records (fact 173–188) as of this
│   │                                 session; includes music_track_id/name,
│   │                                 published_at, category, and (once 48h+
│   │                                 old AND actually has ≥1 real view)
│   │                                 performance + performance_captured_at
│   ├── playlists.json             — legacy, unused
│   ├── usage_log.json             — self-tracked API call counts, COMMITTED
│   │                                 (not gitignored). Current keys observed:
│   │                                 gemini (20 calls), jamendo (10),
│   │                                 youtube_upload (8) + 4 other youtube_*
│   │                                 operation keys, elevenlabs (2 calls,
│   │                                 videos [185,186] — captures the LAST
│   │                                 two ElevenLabs-narrated videos before
│   │                                 the Kokoro swap), pixabay (36 calls,
│   │                                 videos [185–188]), pexels (18 calls,
│   │                                 videos [185–188]), youtube_analytics
│   │                                 (3 calls). No "kokoro" key yet as of
│   │                                 this write-up — see §4's timing note.
│   └── music_blocklist.json       — permanent Jamendo track exclusion list,
│                                     in active use
├── engines/
│   ├── topic_engine.py
│   ├── numbering.py                — idempotent record_video_state();
│   │                                  next_fact_number in videos.json is
│   │                                  only a fallback SEED, not
│   │                                  authoritative — the real next number
│   │                                  is derived by scanning existing
│   │                                  topics/videos, so seeing this field
│   │                                  "stuck" at an old value is normal,
│   │                                  not a bug
│   ├── script_engine.py
│   ├── gemini.py                   — get_unique_topic()/
│   │                                  generate_candidate_topic() accept
│   │                                  performance_context
│   ├── analytics.py                — 48h+ performance capture, retention
│   │                                  digest builder — see §3 step 1 for
│   │                                  the verified zero-view nuance
│   ├── kokoro.py                   — CURRENT narration engine. Local/offline
│   │                                  via Kokoro-82M. Logs a self-tracked
│   │                                  "videos narrated" count (success-only).
│   │                                  Requires the espeak-ng SYSTEM package.
│   ├── elevenlabs.py                — PREVIOUS narration engine. No longer
│   │                                  imported by main.py, no longer checked
│   │                                  by either dashboard. Kept as an easy
│   │                                  rollback path.
│   ├── captions.py
│   ├── timeline.py
│   ├── footage.py                  — Pixabay/Pexels calls logged to
│   │                                  usage_tracker with fact_number
│   ├── renderer.py
│   ├── metadata.py                 — REWRITTEN this session — see §7
│   ├── music.py                     — usage_tracker + blocklist wired in
│   ├── notifications.py             — Gmail SMTP failure emails
│   ├── usage_tracker.py             — log_call(service, fact_number=...)
│   └── youtube.py                   — SCOPES includes yt-analytics.readonly;
│                                       credentials exposed for analytics.py
│                                       reuse
├── check_usage.py                  — local dashboard script. Kokoro card
│                                      (not live-checked, self-tracked count
│                                      only) replaces the old ElevenLabs
│                                      live-quota check. Pexels/Pixabay
│                                      checks now send a random cache-busting
│                                      query param + Cache-Control: no-cache
│                                      — see §6 item 18.
├── blocklist_track.py              — standalone: blocklist a Jamendo track
├── rerun_footage.py / rerun_footage_wombats.py — standalone historical re-runs
├── playwright_login.py / related_video.py — Related Video prototype, SHELVED
├── README.md                       — kept in sync this session, see §11
└── .github/workflows/
    └── daily-video.yml             — see §9, §10
```

---

## 5b. Repo structure — `you-never-knew-dashboard` (separate repo)

```text
you-never-knew-dashboard/
├── index.html                     — renders cards generically from whatever
│                                     the function returns; no ElevenLabs-
│                                     specific markup existed here to begin
│                                     with, so no change was needed for the
│                                     Kokoro swap
├── netlify.toml
└── netlify/
    └── functions/
        └── usage.js               — checkElevenLabs() REMOVED entirely
                                       (along with the now-dead maskKey()
                                       helper it alone used); replaced with
                                       checkKokoro(log), a simple synchronous
                                       function (not async — no network
                                       call) reading the self-tracked count.
                                       checkPexels()/checkPixabay() now send
                                       a random cache-busting query param +
                                       Cache-Control: no-cache — see §6 item 18.
```

Netlify env vars (separate credential store from GitHub Secrets):
`PEXELS_API_KEY`, `PIXABAY_API_KEY`, `GITHUB_REPO=Tobifunmi/you-never-knew-automation`.
`ELEVENLABS_API_KEY` is still set in Netlify (harmless, unused — nothing
reads it anymore).

`usage.js` fetches `database/usage_log.json` fresh from
`raw.githubusercontent.com` on every request — genuinely live on every
page reload.

---

## 6. Bug history — chronological, all fixed/resolved

*(Items 1–15 preserved from the prior version of this document —
unchanged.)*

1. **Fact 174 near-data-loss bug.** Playlist step used to run before
   `record_video_state()`. Fixed: record+complete-topic now runs
   immediately after upload, before playlist logic.
2. **Narrow exception handling** — broadened to `except Exception`.
3. **Footage failures used `raise SystemExit`** — fixed to
   `raise FootageError`.
4. **Stage A/B sat outside the pipeline's `try` block** — fixed,
   guarded by a `topic_reserved` flag.
5. **Wombats (Fact 174) footage repetition** — pre-`exclude_ids` fix,
   re-run locally.
6. **Pangolins (Fact 175) duplicate/bad-footage uploads** — same root
   cause as #5, resolved.
7. **Jamendo hard duration requirement caused failures** — fixed:
   prefers full-length, falls back to longest ≥15s + loops.
8. **`daily-video.yml`'s cron claimed fixed but wasn't** — verified
   false by reading the real file. **As of this session it is
   deliberately commented out again**, by repeated explicit
   instruction — most recently re-confirmed when switching the
   schedule itself from Mon/Thu to daily while keeping it inert. Don't
   treat either "on" or "off" as permanent without re-checking.
9. **`daily-video.yml`'s commit-back step never included
   `usage_log.json`** — fixed, plus the `.gitignore` exclusion reversed.
10. **Dashboard repo folder structure wrong on first deploy** — fixed.
11. **Statue of Liberty (Fact 180) — real YouTube Content ID claim.**
    Resolved manually (re-recorded with different music, re-uploaded).
    Structural fix: `music.py` now records `track_id`/`track_name` per
    video, plus a persistent blocklist.
12. **Jamendo transient failure with misleading error message** —
    fixed: checks `headers.status`, raises Jamendo's real error.
13. **Category-guessing defaulted 46% of videos to "Amazing Facts"** —
    see §7.
14. **YouTube Analytics OAuth scope missing** — `invalid_scope`
    RefreshError. Root cause: YouTube Analytics API not enabled in
    Google Cloud Console (separate from YouTube Data API v3). Fixed:
    enabled it, fresh `token.json` re-auth.
15. **CI secret name mismatch** — workflow read `secrets.TOKEN_JSON`,
    the actually-created secret was `YOUTUBE_TOKEN_JSON`. Fixed:
    workflow now reads `secrets.YOUTUBE_TOKEN_JSON`.
16. **ElevenLabs dashboard card stuck on HTTP 401 after key rotation**
    despite the key testing valid via direct curl. Root cause: invisible
    whitespace from a Netlify UI copy-paste. Fixed by re-pasting
    cleanly; a defensive `.trim()` was added at the time but has since
    been **removed entirely along with the rest of the ElevenLabs check**
    once the narration engine swapped to Kokoro (item 19 below).
17. **YouTube Data API dashboard card text overflowing its card
    boundary** — redundant embedded URLs in status text, no wrap
    handling. Fixed: removed redundant URLs, added
    `overflow-wrap: break-word` CSS safety net.
18. **Pexels dashboard "used" quota frozen at exactly 562** across
    multiple page reloads, despite self-tracked real usage climbing
    9→18 calls in the same window — a near-identical *symptom* to item
    16 (ElevenLabs 401) but a **genuinely different root cause**, worth
    not conflating: this was NOT a key mismatch. The check always sent
    the identical query (`"nature"`, `per_page=1`). Confirmed root
    cause empirically: Pexels was serving a cached response for that
    repeated identical query, including frozen rate-limit headers from
    whenever that response was first cached. **Verified fixed** by the
    user directly: after adding a random cache-busting query param +
    `Cache-Control: no-cache` and reloading twice, the number moved
    from 562 → 102 and the reset date jumped forward to a fresh
    monthly cycle (2026-08-25 → 2026-09-19), confirming it's now
    reading real live data. The same defensive fix was applied to
    Pixabay's check too, pre-emptively — its number hadn't shown the
    symptom, but it had the identical repeated-query pattern.
19. **ElevenLabs replaced with Kokoro-82M as the narration engine** —
    see §4 for full detail. Not a "bug" exactly, but listed here for
    chronological completeness since it triggered cascading dashboard
    changes (items above).

---

## 7. Category-guessing fix (`engines/metadata.py`, prior session,
   unchanged this session — preserved for completeness)

**The bug**: `_wordnet_category()` only ever checked the topic's FIRST
word — broke on articles ("The Dead Sea") and on topics where the
category-bearing word wasn't first ("Giant's Causeway"). Verified:
6/13 (46%) were defaulting to "Amazing Facts" before the fix.

**The fix**: scans every non-stopword word, left to right, trying each
against `HYPERNYM_CATEGORY_MAP`. Added stopword list, landmark/
geological/chemistry keyword coverage, new hypernym mappings
(`chemical_element.n.01`, `road.n.01`, `sculpture.n.01`), and an
explicit `"bermuda triangle"` keyword override.

**Verified**: 0/13 fall to default post-fix. Spot-checks (Great Wall
of China, Eiffel Tower, Roman Colosseum, etc.) all resolve correctly.

**Accepted residual limitation**: single ambiguous words can still
misresolve (e.g. "Chess" → Nature Facts via a WordNet plant sense).
Not fixed — unlikely as a real topic, not worth a new category for one
word.

**This fix only affects future videos** — the 6 pre-existing "Amazing
Facts" entries were not retroactively reclassified, neither in
`videos.json` nor on YouTube's actual playlists. A backfill script was
offered but not requested/built.

---

## 8. Deliberately deferred work

**Shorts "Related Video" (End Screen).** No public API for Studio's
End Screen setting. Decision made: always link to the immediately-
previous fact's video. Mechanism undecided — a Playwright/Studio
browser-automation prototype exists but was explicitly shelved before
a working headed run. Simpler alternative not yet built: a link in the
video description instead. Do not resume without explicit direction.

**Zack D Films-style production skill.** Explored via Higgsfield MCP
for a separate, more elaborate 3D-animated short-form pipeline;
stalled at a Higgsfield billing barrier. Not connected to the You
Never Knew pipeline — separate effort, separate status.

## 8b. Google AI Plus/Pro student offer — researched, not adopted

The user asked whether access to Google's student AI subscription
offer (region-dependent: AI Plus outside the US, AI Pro for US
students) would help this pipeline. Conclusion, reached by research
rather than assumption:

- **AI Plus** (what a Nigeria-based student would get) bundles more
  usage in Google's own consumer apps (Gemini chat, Gmail/Docs/Sheets,
  storage) — it does NOT include any Google Cloud credit or elevated
  AI Studio quota. The pipeline's `GEMINI_API_KEY` calls (via the
  `google-genai` SDK) are on a completely separate quota system from
  the consumer app subscription, so AI Plus would change nothing about
  the pipeline.
- **AI Pro** (US-only for students) DOES bundle a real, if modest,
  $10/month Google Cloud credit applicable to Gemini API billing, plus
  higher AI Studio playground rate limits — but only after explicitly
  enabling Cloud Billing on the project (which also flips the key from
  free-tier to paid-tier pricing/limits). Assessed as low-value at
  current/planned request volume (2x/week → daily, one Gemini call
  cycle per video) — the free tier's request-based limits aren't
  remotely close to being the bottleneck for this pipeline.
- **Net conclusion**: not pursued. The narration cost/limit problem
  this prompted the broader conversation into was real, but was
  actually solved by the Kokoro swap (§4), not by a Google subscription
  of any tier.

---

## 9. Credentials / environment variables / GitHub Secrets

**Automation repo** — local `.env` + GitHub Secrets: `GEMINI_API_KEY`
(model: `GEMINI_MODEL` env var, defaults to `gemini-3.6-flash`, free
tier), `PEXELS_API_KEY`, `PIXABAY_API_KEY`, `JAMENDO_CLIENT_ID`,
`GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`. **`ELEVENLABS_API_KEY` /
`ELEVENLABS_VOICE_ID` are no longer required** — left as GitHub
Secrets harmlessly (removed from the pipeline execution step's `env:`
block in the workflow, but the secrets themselves weren't deleted).
`KOKORO_VOICE_ID` / `KOKORO_SPEED` / `KOKORO_PAUSE_SECONDS` are
optional overrides with sane defaults, not required to be set anywhere.

YouTube OAuth: `credentials.json` (never committed) + `token.json`
restored in CI from the **`YOUTUBE_TOKEN_JSON`** GitHub Secret (name
fixed this session, must carry BOTH the upload scope AND
`yt-analytics.readonly`).

**Dashboard repo (Netlify)** — separate store: `PEXELS_API_KEY`,
`PIXABAY_API_KEY`, `GITHUB_REPO=Tobifunmi/you-never-knew-automation`.
`ELEVENLABS_API_KEY` still present but unused. When rotating any key,
paste carefully — a copy-paste whitespace issue caused a real,
hard-to-diagnose 401 earlier this session (see §6 item 16) before the
ElevenLabs check was removed entirely.

---

## 10. `daily-video.yml` — current real state (verified, not assumed)

```yaml
on:
  #schedule:
  #- cron: '0 10 * * *'  # Every day at 10:00 UTC

  # Manual trigger button in GitHub Actions UI
  workflow_dispatch:
```

**Deliberately commented out**, schedule changed FROM `'0 10 * * 1,4'`
(Mon/Thu) TO `'0 10 * * *'` (daily) this session — but the "commented
out" part is unchanged, by explicit repeated instruction: "I'll change
the cron to daily, but still keep it commented out until I'm ready. I
still have unpublished videos for now." Do not enable without being
asked. Only `workflow_dispatch` currently triggers a run.

Steps, in order: checkout → setup Python 3.11 → **install ffmpeg AND
espeak-ng** (single combined step now) → install pip deps → **cache
Hugging Face model weights** (`actions/cache`, path
`~/.cache/huggingface`, keyed on `hashFiles('requirements.txt')`) →
download WordNet corpus → restore `topics.json`/`videos.json`/
`token.json` from Secrets → run `python main.py run --production` with
secrets injected as env vars (**no longer includes
ELEVENLABS_API_KEY/ELEVENLABS_VOICE_ID**) → commit-back step
(`if: always()`) — `git add database/topics.json database/videos.json
database/usage_log.json`, commit, push, all with `|| true`.

**Daily-cadence feasibility check performed this session** (before the
schedule was changed): Pexels ~4.5 calls/video → ~135/month at daily
cadence against a 25,000/month limit, trivial. Pixabay has no monthly
cap (rolling 60s window only). YouTube Data API ~1,750 units/video
against 10,000/day budget → ~17.5%/day, comfortable. Gemini's
request-based free tier is nowhere close to being a constraint at 2-3
calls/day. **Jamendo is the one honest asterisk**: no published
official quota exists; the only evidence is empirical (the project
already discovered a real, hittable limit during *concentrated local
testing*). Daily production (one spaced-out call every 24h) is a much
gentler pattern than what already succeeded during testing, so it's
assessed as very likely safe — but not verified/guaranteed the way the
others are. Worth watching the dashboard for the first couple of weeks
after cron is ever actually enabled.

---

## 11. Documentation state

`README.md` in the automation repo has been kept current across
multiple passes this session — most recently updated to reflect: the
Kokoro swap (status table, Requirements, project structure tree,
Known Limitations), the dashboard's Kokoro/ElevenLabs card swap, the
Pexels caching bug and its fix, and the cron's current daily-but-
commented-out state (Trigger section shows the real current line, not
a stale one). Treat the README as reliably current as of this session.

**A committed copy of an earlier version of this exact document**
lives at `/MASTER_CONTINUATION_PROMPT.md` in the automation repo root
(added by the user, not automatically kept in sync). It predates the
entire Kokoro swap and dashboard-caching-fix work — this document is
the current one; consider replacing the committed file with this
version so the repo's own copy doesn't mislead a future session that
reads it directly instead of being handed this prompt.

---

## 12. Working style / operating principles

Each of these has concretely prevented or caught a real problem in
this project's actual history:

- **Verify against actual files/logs before treating something as
  done.** Recurred again this session in a new form: the "185 got
  analytics, why didn't 186" question was answered by actually
  querying `videos.json` and reasoning through the timestamps and
  Analytics API behavior, not by assuming Stage A0 was broken.
- **Don't conflate similar-looking symptoms with the same root
  cause.** The Pexels "frozen 562" (§6 item 18) looked identical on
  the surface to the earlier ElevenLabs 401 (§6 item 16) — both
  presented as "the live check isn't reflecting reality" — but were
  different bugs (server-side response caching vs. a whitespace-
  corrupted credential). Diagnosed and fixed as genuinely distinct
  issues rather than pattern-matching to the previous fix.
- **No manual overrides for anything unattended.** Fixes are either
  genuinely automated or explicitly flagged as needing a one-time
  human step (Playwright login, a fresh OAuth re-auth for a new scope,
  installing `espeak-ng` locally) — never a silent assumption someone
  will intervene during a scheduled run.
- **Prefer free/offline over paid/AI where genuinely sufficient** —
  the Kokoro swap this session is the largest-yet application of this
  principle, and was chosen explicitly citing the same reasoning
  already established for WordNet-over-AI-classification and
  SMTP-over-OAuth.
- **Be honest about what was and wasn't actually verified.** The
  Kokoro integration work was explicit throughout about the boundary
  between what the assistant's sandbox could confirm (imports, error
  handling, no naming collisions) and what it genuinely could not
  (real audio generation, voice quality) — that gap was only closed by
  the user's own real-world test and direct feedback ("it sounded the
  same"), not assumed away.
- **Isolate failure domains.** A failure in one stage should never
  retroactively invalidate work that already genuinely succeeded.
- **Accept known, narrow, low-probability limitations rather than
  over-engineering fixes** — but always name them explicitly (§7 fix
  detail, §3's zero-view analytics nuance, §10's Jamendo asterisk).
- **When infrastructure changes what's true, go back and fix the
  earlier advice that's now wrong** — recurred again this session:
  removing the ElevenLabs dashboard checks entirely once they became
  dead code, rather than leaving them silently stale.
- **Patches, not direct pushes, from this assistant.** No push
  credentials to either repo — all code changes are delivered as `git
  format-patch` files, applied locally via `git am <file>.patch` then
  `git push origin main` by the user. Expect this pattern to continue.
