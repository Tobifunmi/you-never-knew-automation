# MASTER CONTINUATION PROMPT — "You Never Knew" Automated YouTube Shorts Factory

Use this as full context in a new conversation. Reflects the verified state of
the project as of **12 Sep 2026**. This version supersedes the previous
`MASTER_CONTINUATION_PROMPT.md` (dated 28 Aug 2026, committed in the automation
repo root) — that document is now out of date in several important ways
described below. Consider re-committing this version over it.

**Important gap to flag honestly**: there is a documentation hole between
28 Aug 2026 (the previous document's date) and 12 Sep 2026 (this one). A
real-time scheduling feature (`engines/scheduling.py`, `config.json`'s
`scheduling` block, and `publish_at` support in `engines/youtube.py` and
`main.py`) exists live in the repo and is clearly well-built and battle-tested
— but it was discovered by reading the actual repo code directly in this
session, not by anything said in this conversation or the 28 Aug document.
Some other session in between must have built it. Treat the live code as
ground truth over any assumption either document makes about what's "not yet
built."

GitHub username: **Tobifunmi** (capitalized). Automation repo:
`github.com/Tobifunmi/you-never-knew-automation` (public). Dashboard repo:
`github.com/Tobifunmi/you-never-knew-dashboard` (public). Live dashboard:
`https://you-never-knew.netlify.app/`.

Local dev machine: Windows 10/11, PowerShell, two separate local repo folders
— `C:\Users\user\Documents\You Never Knew` (automation) and
`C:\Users\user\Documents\You Never Knew - Dashboard` (dashboard).

**How code changes reach the repo**: this assistant has no push credentials.
Historically, changes were delivered as `git format-patch` files, applied
locally via `git am`, then pushed by the user. As of this session, this
assistant can also **read** the public repo directly (`raw.githubusercontent.com`,
`api.github.com` are reachable) to verify real code before proposing changes —
worth doing before writing any patch, per the project's long-standing
"verify against actual files before treating something as done or broken"
principle. Still no write/push access.

---

## 1. What this project is

A fully automated production and publishing pipeline for the YouTube channel
**You Never Knew** — "5 Facts You Didn't Know About [Topic]" YouTube Shorts.
Topic selection, script writing, narration, footage, captions, rendering,
background music, metadata, YouTube upload, scheduling, playlist assignment,
database recording, 48h+ performance tracking, and failure notification all
run on GitHub Actions, triggered on a daily schedule via **cron-job.org**
(not GitHub's own `schedule:` cron — see §4d for why). Can still be run
locally on Windows for development/testing.

**As of 12 Sep 2026 (verified via YouTube Studio screenshot)**: the channel
is live and posting publicly on a real cadence. Most recently confirmed
state:
- Fact 192 ("Chewing Gum") — public, published Sep 12, 460 views
- Fact 191 ("Popcorn") — public, published Sep 11, 11 views
- Fact 190 ("Bicycles") — public, published Sep 10, 346 views
- Fact 188 ("Stonehenge") — public, published Sep 8, 35 views
- Fact 187 ("Solar Eclipses") — public, published Sep 7, 342 views
- Fact 193 ("Quicksand") — **scheduled**, Sep 13, private/pending
- Fact 194 ("Pistol Shrimp") — **scheduled**, Sep 14, private/pending, still processing to HD at time of screenshot

The channel had 17 unlisted test videos (facts 173–189) as of the 28 Aug
document; it has since gone public and progressed to at least fact 194. The
full history of facts 189–192 (when exactly the switch to public/production
happened, what if anything went wrong along the way) is **not documented
anywhere in this conversation or the prior master prompt** — a real gap.
`database/videos.json` and `usage_log.json` in the repo are the source of
truth if that history is ever needed.

---

## 2. Current status

| Stage | Status |
|---|---|
| YouTube publisher (OAuth, upload, scheduling, playlists, DB recording) | ✅ Done, live in production |
| Scheduling (`engines/scheduling.py`, real `status.publishAt`) | ✅ Done, live — see §4g. Maintains a rolling one-video-ahead buffer: each run schedules the next video `cadence_hours` (24h) after the latest scheduled/live video's real anchor time on YouTube, cross-checked against local DB to catch drift |
| Narration — Kokoro-82M (local/offline, no API key, no char cap) | ✅ Done |
| Footage (Pixabay → Pexels waterfall) | ✅ Done |
| Captions (local Whisper, burned-in ASS) | ✅ Done |
| Render (FFmpeg, 1080×1920) | ✅ Done |
| Background music (Jamendo, loops short tracks, blocklist-aware) | ✅ Done — `+`-encoding bug fixed (§6 item 20) |
| Topic engine + fact numbering | ✅ Done |
| Autonomous topic/script generation (Gemini) | ✅ Done |
| 48h YouTube Analytics feedback loop (Stage A0) | ✅ Done, gated on real live-publish time (§4a) |
| Category-guessing fix (WordNet, scans every word) | ✅ Done |
| API usage dashboard (Netlify) | ✅ Done |
| Kokoro dashboard card | ✅ Done |
| Full unattended automation trigger | ✅ **Live** — cron-job.org calls the GitHub Actions `workflow_dispatch` API on a schedule (§4d). GitHub's own `schedule:` block in `daily-video.yml` remains commented out/unused by design. |
| YouTube OAuth token stability | ✅ Fixed this session — app moved from "Testing" to "In production" in Google Auth Platform, eliminating the 7-day forced refresh-token expiry (§4e) |
| Secret leak in local git history | ✅ Resolved this session, `.gitignore` hardened (§4f) |
| Email failure notifications (Gmail SMTP) | ⚠️ Still unresolved as of 28 Aug (`WinError 10060`, local network-level). Status since then unknown — not discussed this session. |
| Shorts "Related video" End Screen | 🔜 Deliberately deferred |
| Playlist/record ordering bug | ✅ Fixed (historical) |

---

## 3. Pipeline stages, actual execution order (`main.py :: run_pipeline()`)

Verified directly from the live `main.py` this session.

0. **Config load** — `config.json`. Key fields: `starting_fact_number: 172`,
   `title_template: "Fact {fact_number}: 5 Facts You Didn't Know About {topic}"`,
   `youtube.privacy_status: "unlisted"` (fallback only — see step 10 below for
   what actually governs privacy), `youtube.category_id: "27"` (Education),
   `youtube.auto_create_playlists: true`, and **`scheduling: {"enabled": true,
   "cadence_hours": 24}`**.
1. **Stage A0 — 48h+ performance capture.** Runs first, before topic
   selection, using the same authenticated `YouTubePublisher` instance reused
   throughout the run. Never fatal. A video only becomes eligible once
   `analytics.py` confirms via the Data API it's really `public` — the 48h
   window is measured from YouTube's real `snippet.publishedAt`
   (`live_published_at`), not upload-completion time (see §4a).
2. **Stage A/B — Topic + script ingestion.** Manual (script file) or
   autonomous (`gemini.get_unique_topic(performance_context=...)` +
   `gemini.generate_script()`). Fact number assigned, topic reserved.
3. **Stage C — Narration.** `engines/kokoro.py`, local/offline.
4. **Transcription + timeline** — local Whisper, `build_segment_timeline()`.
5. **Stage D — Footage.** Pixabay → Pexels → broad-topic fallback → generic
   last resort. Raises `FootageError` on failure (not `SystemExit` — that was
   a historical bug, see §6 item 3).
6. **Stage E — Captions file** (ASS).
7. **Stage F — Render.** Normalize → concatenate → background music →
   burn in captions. Can raise `MusicError` and abort here.
8. **Stage G — Metadata.** Title/description/tags, WordNet-based playlist
   categorization.
9. **Stage H — Compute scheduling, then upload.**
   ```python
   scheduling_enabled = production and config.get("scheduling", {}).get("enabled", False)
   publish_at = None
   if scheduling_enabled:
       publish_at = scheduling.compute_next_publish_at(publisher, config)

   privacy_status = "private" if scheduling_enabled else ("public" if production else "unlisted")
   ```
   - **Local dev run, no `--production`**: always `unlisted`, immediate,
     never scheduled.
   - **Production run, scheduling enabled (current real config)**: always
     `private` + a real `status.publishAt` 24h after the latest
     scheduled/live video's true anchor time (see §4g for the exact
     algorithm). **This applies even to a completely empty backlog** —
     there is no code path today that publishes a production video
     instantly live; every production upload goes through the scheduler.
   - `publish_at`, when set, forces `effective_privacy = "private"`
     regardless of what was passed in, inside `youtube.py`'s
     `upload_video()` — YouTube itself requires this.
10. **Record + complete topic.** Runs immediately after upload, before
    playlist logic (load-bearing ordering, fixes the historical Fact 174
    near-data-loss bug — see §6 item 1). `numbering.record_video_state()`
    stores `state` as `"scheduled"` / `"published"` / `"uploaded"`
    depending on the branch above, plus `scheduled_publish_at` (read back
    by `scheduling.py` on the next run).
11. **Stage I — Playlist.** Isolated `try/except`, never re-raises — a
    playlist failure sends its own failure email but never touches the
    already-saved upload record.
12. **Failure path** — outer `except Exception`. Sends a failure email
    (Gmail SMTP — currently unreliable, see §6 item 21), releases the topic
    reservation only if it was actually reserved.

---

## 4. Detailed history, chronological

### 4a. Analytics 48h-gating fix (historical, ~28 Aug session)
`analytics.py`'s eligibility check now confirms via the YouTube Data API that
a video's real `status.privacyStatus` is `"public"` before starting its 48h
clock, and anchors that clock on YouTube's own `snippet.publishedAt`
(cached as `live_published_at`) rather than the pipeline's own
upload-completion timestamp. Matters precisely because scheduled videos
(§4g) can sit private for a long time after upload before going live.
Confirmed applied and pushed (commit `db1d1af`).

### 4b. Local-vs-GitHub-Actions provenance (historical, resolved 28 Aug; reconfirmed this session)
Earlier local runs (facts 187, 188) had been mis-described as "through
GitHub" but were actually local (`narration_path` showed Windows paths, not
Actions runner paths). This session went further: a **real GitHub Actions
run was triggered and completed via the cron-job.org dispatch call**
(§4d), which is the first fully confirmed end-to-end Actions execution
in this project's history — a genuine milestone, not just a corrected
misstatement anymore.

### 4c. Fact 189 ("Bicycles") Jamendo failure + fix (historical, 28 Aug session)
Failed once on a `MusicError` (no loopable Jamendo track found), retried
successfully. Root cause found and fixed: `engines/music.py`'s `VIBE_MAP`
joined multi-tag searches with a literal `+`, which `requests` percent-encodes
to `%2B`, causing Jamendo to search for one bogus literal tag instead of two
real tags — every "Tier 1" topic-specific search had silently been returning
zero results since the tag system was introduced. Fixed: switched to
space-joined tags (`requests` correctly encodes a raw space as `+` on the
wire, matching Jamendo's expected format). Confirmed applied and pushed.

### 4d. Switch to cron-job.org as the scheduling trigger (this session)
**Why**: GitHub Actions' own `schedule:` cron trigger has a known reliability
problem (delays, skipped runs on low-activity repos) and — separately — had
never been confirmed to actually fire successfully at all for this project
(§4b). Rather than fight GitHub's scheduler, the fix was to leave
`daily-video.yml`'s `schedule:` block commented out (as it already was) and
instead have an external service call the **`workflow_dispatch` REST API**
on a schedule — functionally identical to clicking "Run workflow" by hand,
every day, automatically.

**Setup**: cron-job.org job "You Never Knew daily trigger" —
- URL: `https://api.github.com/repos/Tobifunmi/you-never-knew-automation/actions/workflows/daily-video.yml/dispatches`
- Method: `POST`
- Headers: `Authorization: Bearer <fine-grained GitHub PAT>` (no colon after
  "Bearer" — this was an early mistake that caused a 401, see below),
  `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`,
  `Content-Type: application/json`
- Body: `{"ref": "main"}`
- Schedule: daily, timezone Africa/Lagos
- The GitHub PAT is fine-grained, scoped to just this repo, with **Actions:
  Read and write** permission. It lives only in cron-job.org's job config —
  never committed anywhere. **No expiration date was recorded in this
  conversation — worth checking/rotating before it lapses.**

**Debugging history worth remembering**:
- First test run failed `401 Unauthorized` — the Authorization header value
  had been entered as `Bearer: github_pat_...` (colon after "Bearer"), which
  GitHub can't parse as a valid token. Fixed by removing the colon (the
  header **key** field already supplies `Authorization:` — the **value**
  field should be exactly `Bearer <token>`, space only, no colon).
- After that fix, the dispatch call succeeded and Actions genuinely started
  a run — confirming this mechanism works.

`daily-video.yml` itself was **not modified** for any of this — it still
only declares `workflow_dispatch:` as its trigger; cron-job.org calling that
endpoint is indistinguishable to GitHub from a human clicking the button.

### 4e. YouTube OAuth refresh token expiry incident (this session)
The first real end-to-end Actions run (triggered via cron-job.org) failed
with `google.auth.exceptions.RefreshError: invalid_grant: Token has been
expired or revoked`. A local re-run of `python main.py run` failed
**identically** — confirming the refresh token itself was dead, not
something specific to the Actions environment.

**Root cause**: the Google Cloud OAuth consent screen (now called "Google
Auth Platform" in the Cloud Console UI) was in **Testing** publishing
status. Google forcibly expires refresh tokens after 7 days for apps in
that state, regardless of use.

**Fix applied**:
1. Deleted the local stale `token.json` (simply re-running without deleting
   it first doesn't help — `youtube.py`'s `authenticate()` calls
   `creds.refresh()` on the existing file before ever falling through to a
   fresh interactive login, so a dead token crashes instead of triggering
   re-auth).
2. Ran `python main.py run` locally with no token file present, which
   correctly forced a fresh interactive browser login and produced a new
   `token.json`.
3. Copied its contents into the `YOUTUBE_TOKEN_JSON` GitHub secret,
   replacing the old value.
4. Separately, in Google Cloud Console → **Google Auth Platform → Audience**,
   confirmed Publishing status now reads **"In production"** (with a
   "Back to testing" button present, meaning it had already been switched at
   some point — possibly during an earlier, undocumented attempt at Google's
   verification process, evidenced by a "Branding verification issues" panel
   that referenced an unresolved domain-ownership check for
   `https://you-never-knew.netlify.app/`).

**Decision made**: leave Publishing status as "In production" — this alone
fixes the 7-day forced expiry, since that only applies to apps in Testing.
**Do not pursue full Google verification (CASA security assessment)** for
the `youtube.upload` restricted scope — that process is built for real
third-party companies distributing an app publicly, not proportionate for a
solo automation project, and was correctly abandoned mid-flow (the
"Branding verification issues" panel was closed via Cancel rather than
continuing either resolution path).

**Ongoing note**: User type is "External," under the 100-user cap, so a
Google "unverified app" warning screen still appears at login time — expected
and harmless for a personal-use app; click "Advanced" → "Go to [app] (unsafe)"
to proceed on any future manual re-auth. Being "In production" itself should
prevent the 7-day expiry from recurring; the manual re-auth pattern for a
Testing-mode app is no longer expected to be a routine chore.

### 4f. Local git history secret leak (this session)
While cleaning up the dead token file, `token.json` had been renamed to
`token.json.bak` and **committed** (with real, if by-then-expired, OAuth
client ID/secret/refresh token inside) in a local-only commit that hadn't
yet reached GitHub. A later commit deleted the file, but `git push` was
correctly rejected by **GitHub push protection** (GH013), since the secret
was still readable in the earlier commit's history even though a later
commit removed it.

**Fix**: since none of the offending commits had reached GitHub yet,
history was safely rewritten locally:
1. `git log origin/main..HEAD --oneline` to identify the unpushed commits.
2. `git reset --soft origin/main` — rewound the branch to match GitHub
   while keeping all real file changes staged on disk, erasing the
   problem commits from history without losing any work.
3. Added `token.json`, `token.json.bak`, and the OAuth
   `credentials.json`/`client_secret*.json` filename to `.gitignore`.
4. Recommitted and pushed cleanly.

Since the push was rejected before ever reaching GitHub, the secret was
never actually exposed publicly — no credential rotation was necessary
purely because of this incident (separately, the refresh token itself was
already dead per §4e).

### 4g. Scheduling engine — `engines/scheduling.py` (discovered this session, not built in this conversation)
Full module read directly from the live repo. Not present in the 28 Aug
document, which explicitly listed "Scheduled/timed YouTube publishing" as
**not built yet**. Must have been added in an undocumented session between
28 Aug and this one.

**What it does** (`compute_next_publish_at(publisher, config)`):
1. Reads `cadence_hours` from `config.json` (currently `24`).
2. Looks up the latest local video record
   (`numbering.get_latest_video_record()`). If there's no record or no real
   `youtube_id` yet (fresh channel / only unlisted test uploads so far),
   returns `now + cadence_hours` — **note: still schedules, does NOT publish
   immediately**, even on a completely empty backlog.
3. Otherwise, calls `publisher.get_video_status(youtube_id)` — a real Data
   API lookup — rather than trusting the local database alone. If YouTube
   has no record of it at all, raises `SchedulingDriftError` rather than
   silently guessing.
4. Determines an anchor time:
   - If the latest video is currently `private` with a real `publishAt` set
     → anchor = that `publishAt`.
   - If it's already `public` → anchor = its real `snippet.publishedAt`.
   - Otherwise (unlisted, or manually un-scheduled in Studio) → anchor =
     `now`.
5. Cross-checks the locally recorded `scheduled_publish_at` against what
   YouTube actually reports; if they disagree by more than 60 seconds
   (e.g. a manual Studio edit happened out-of-band), raises
   `SchedulingDriftError` rather than scheduling on top of a wrong
   assumption — deliberately named after the exact class of bug that once
   caused a historical fact-numbering collision (facts 175–184, referenced
   in the module's own docstring, not otherwise detailed in either master
   prompt).
6. Returns `max(anchor, now) + cadence_hours` as the next video's
   `publishAt`.

**Net effect / design intent** (from the module's own docstring): keeps a
rolling one-video-ahead buffer at all times, so a daily cron trigger is
safe even if the pipeline run itself is slow, and there's no scenario where
the channel goes a day without a queued video **once the buffer already has
something in it**. It explicitly does *not* implement "publish live
immediately if the queue is empty" — every production run schedules,
period, as long as `scheduling.enabled` is true in config. This was flagged
to the user as a real behavior gap versus one way they described their
expectations, but turned out not to matter for the actual state of the
channel (which already had Fact 193 live/anchored when this was checked) —
**worth remembering if the buffer ever genuinely empties out in the
future**, since the current code will still schedule 24h out rather than
publish instantly in that case.

**Verified working, 12 Sep**: YouTube Studio screenshot confirms exactly
two videos currently sitting in the scheduled buffer (Fact 193 → Sep 13,
Fact 194 → Sep 14), consistent with two consecutive daily cron-job.org
triggers having each correctly scheduled 24h past the prior anchor.

---

## 5. Repo structure — `you-never-knew-automation`

Reflects the live repo as read directly this session (`main.py`,
`engines/youtube.py`, `engines/scheduling.py`, `config.json` verified
firsthand; the rest carried over from the 28 Aug document and not
re-verified this session — flagged accordingly).

```text
you-never-knew-automation/
├── main.py                       — orchestrator. Stage A0 (analytics) runs
│                                    first. Stage H now computes scheduling
│                                    before upload — see §3 step 9, §4g.
│                                    VERIFIED LIVE this session.
├── config.json                   — VERIFIED LIVE this session. Now includes
│                                    a "scheduling": {"enabled": true,
│                                    "cadence_hours": 24} block not present
│                                    in the 28 Aug document.
├── config.example.json
├── requirements.txt               — google-api-python-client, google-auth-
│                                    httplib2, google-auth-oauthlib, python-
│                                    dotenv, google-genai, faster-whisper,
│                                    nltk, kokoro>=0.9.4, soundfile, numpy
│                                    (not re-verified this session)
├── MASTER_CONTINUATION_PROMPT.md  — the 28 Aug version is committed here;
│                                    THIS document supersedes it
├── .env                           — LOCAL ONLY, gitignored
├── credentials.json               — Google OAuth desktop app credential,
│                                    gitignored (confirm this filename is
│                                    actually in .gitignore — see §4f, this
│                                    was tightened this session)
├── token.json                     — gitignored, restored from GitHub Secret
│                                    YOUTUBE_TOKEN_JSON in CI. token.json.bak
│                                    also now explicitly gitignored (§4f).
├── database/
│   ├── topics.json
│   ├── videos.json                — not re-read this session; last verified
│                                    state (28 Aug) was 16 successful records
│                                    + 1 released attempt. Current true count
│                                    is at least 194 fact numbers deep with a
│                                    mix of published/scheduled states — see
│                                    §1. Re-read this file directly for the
│                                    real current picture rather than
│                                    trusting either master prompt's count.
│   ├── playlists.json             — legacy, unused
│   ├── usage_log.json             — self-tracked API call counts, committed
│   └── music_blocklist.json       — Jamendo track exclusion list
├── engines/
│   ├── topic_engine.py
│   ├── numbering.py                — record_video_state(),
│   │                                  get_latest_video_record() (the latter
│   │                                  confirmed in use by scheduling.py,
│   │                                  §4g, not independently re-read)
│   ├── script_engine.py
│   ├── gemini.py
│   ├── analytics.py                — 48h gating on live_published_at, §4a
│   ├── scheduling.py                — VERIFIED LIVE this session, full
│   │                                  detail in §4g. compute_next_publish_at(),
│   │                                  SchedulingDriftError.
│   ├── kokoro.py                   — current narration engine
│   ├── elevenlabs.py                — previous engine, kept as rollback,
│                                     unused
│   ├── captions.py
│   ├── timeline.py
│   ├── footage.py
│   ├── renderer.py
│   ├── metadata.py                 — WordNet category-guessing fix, §6/§7
│   ├── music.py                     — Jamendo, VIBE_MAP fix §4c/§6 item 20
│   ├── notifications.py             — Gmail SMTP failure emails; local
│                                     WinError 10060 as of 28 Aug, status
│                                     since unknown
│   ├── usage_tracker.py
│   └── youtube.py                   — VERIFIED LIVE this session.
│                                     SCOPES = [youtube, yt-analytics.readonly].
│                                     upload_video(..., publish_at=None) —
│                                     passing publish_at forces
│                                     privacyStatus="private" regardless of
│                                     the privacy_status arg (YouTube
│                                     requirement). get_video_status(video_id)
│                                     — real Data API status+snippet lookup,
│                                     used by scheduling.py.
├── check_usage.py                  — local dashboard script
├── blocklist_track.py
├── rerun_footage.py / rerun_footage_wombats.py
├── playwright_login.py / related_video.py — Related Video prototype, SHELVED
├── README.md
└── .github/workflows/
    └── daily-video.yml             — VERIFIED LIVE this session (see below).
                                       schedule: block still commented out —
                                       intentionally unused now that
                                       cron-job.org drives triggers (§4d),
                                       not because it's broken.
```

**`daily-video.yml`, current real content** (verified this session,
unchanged from the 28 Aug document except for context around its trigger):

```yaml
on:
  #schedule:
  #- cron: '0 10 * * *'  # Every day at 10:00 UTC

  # Manual trigger button in GitHub Actions UI
  workflow_dispatch:
```

Steps: checkout → setup Python 3.11 → install ffmpeg + espeak-ng → install
pip deps → cache Hugging Face model weights (keyed on
`hashFiles('requirements.txt')`) → download WordNet corpus → restore
`topics.json`/`videos.json`/`token.json` from Secrets → run
`python main.py run --production` (unconditional — every triggered run is a
real production attempt) → commit-back step (`if: always()`), commits
`database/topics.json`, `database/videos.json`, `database/usage_log.json`.

---

## 5b. Repo structure — `you-never-knew-dashboard` (separate repo, not touched this session)

```text
you-never-knew-dashboard/
├── index.html
├── netlify.toml
└── netlify/
    └── functions/
        └── usage.js               — checkKokoro(log) reads the self-tracked
                                       count; checkPexels()/checkPixabay()
                                       use cache-busting params (§6 item 18)
```

Netlify env vars: `PEXELS_API_KEY`, `PIXABAY_API_KEY`,
`GITHUB_REPO=Tobifunmi/you-never-knew-automation`. `ELEVENLABS_API_KEY` still
present but unused. `usage.js` fetches `database/usage_log.json` fresh from
`raw.githubusercontent.com` on every page load.

---

## 6. Bug history — chronological, all fixed/resolved unless noted

*(Items 1–21 preserved from the 28 Aug document, condensed. Items 22–24 new
this session.)*

1. Fact 174 near-data-loss bug — record-before-playlist ordering fix.
2. Narrow exception handling broadened to `except Exception`.
3. Footage failures used `raise SystemExit` — fixed to `raise FootageError`.
4. Stage A/B sat outside the pipeline's `try` block — fixed with a
   `topic_reserved` flag.
5–6. Wombats/Pangolins footage repetition — `exclude_ids` fix.
7. Jamendo hard duration requirement — prefers full-length, falls back to
   longest ≥15s + loops.
8. `daily-video.yml`'s cron claimed fixed but wasn't — verified false by
   reading the real file, repeatedly. **This pattern (claims about the
   workflow file's state not matching reality) recurred conceptually again
   this session** — always re-read the file directly rather than trusting a
   prior summary.
9. Commit-back step missing `usage_log.json` — fixed.
10. Dashboard repo folder structure wrong on first deploy — fixed.
11. Statue of Liberty (Fact 180) Content ID claim — resolved manually,
    structural fix: per-video track_id/name + persistent blocklist.
12. Jamendo transient failure with misleading error message — fixed.
13. Category-guessing defaulted 46% of videos to "Amazing Facts" — see §7
    in the 28 Aug document (WordNet scan-every-word fix, verified 0/13
    fall to default post-fix).
14. YouTube Analytics OAuth scope missing (`invalid_scope`) — fixed by
    enabling the YouTube Analytics API in Cloud Console + fresh re-auth.
15. CI secret name mismatch (`TOKEN_JSON` vs `YOUTUBE_TOKEN_JSON`) — fixed.
16. ElevenLabs dashboard 401 from invisible copy-paste whitespace — fixed
    (moot now, ElevenLabs check removed entirely).
17. YouTube Data API dashboard card text overflow — fixed.
18. Pexels dashboard quota frozen due to a cached identical query — fixed
    with cache-busting param + `Cache-Control: no-cache`. Same fix
    pre-emptively applied to Pixabay.
19. ElevenLabs → Kokoro-82M narration engine swap.
20. Jamendo `VIBE_MAP` `+`-encoding bug — see §4c. Fixed, confirmed pushed.
21. **DEFERRED, not investigating unless it recurs** — Gmail SMTP failure
    notifications timing out locally (`WinError 10060`), likely a local
    firewall/ISP/VPN issue. Status since 28 Aug unknown.
22. **NEW, this session** — cron-job.org Authorization header 401: value
    was entered as `Bearer: <token>` (extra colon) instead of `Bearer
    <token>`. Fixed.
23. **NEW, this session** — YouTube OAuth refresh token expiry due to
    Testing publishing status (7-day forced expiry). Fixed by moving to
    "In production" status + fresh re-auth. Full detail §4e.
24. **NEW, this session** — `token.json.bak` briefly entered local git
    history with real (if dead) credentials inside; caught by GitHub push
    protection before ever reaching GitHub. Resolved via `git reset --soft`
    + hardened `.gitignore`, no rotation needed. Full detail §4f.

---

## 7. Category-guessing fix (`engines/metadata.py`, historical, unchanged)

`_wordnet_category()` previously only checked a topic's first word, causing
46% (6/13) of videos to default to "Amazing Facts." Fixed to scan every
non-stopword word left to right against `HYPERNYM_CATEGORY_MAP`, with added
landmark/geological/chemistry keyword coverage and an explicit "bermuda
triangle" override. Verified 0/13 fall to default post-fix. Residual known
limitation: single ambiguous words can still misresolve (e.g. "Chess" via a
WordNet plant sense) — accepted, not worth a fix for one-off cases. This fix
was **not retroactive** — the 6 pre-existing "Amazing Facts" entries were
never reclassified.

---

## 8. Deliberately deferred work

- **Shorts "Related Video" End Screen.** No public API for Studio's End
  Screen setting. Decision: always link to the immediately-previous fact's
  video; mechanism undecided (a shelved Playwright prototype exists). Do
  not resume without explicit direction.
- **Zack D Films-style production skill** (via Higgsfield MCP) — separate
  effort, stalled at a billing barrier, unrelated to this pipeline.
- **Google AI Plus/Pro student offer** — researched and explicitly not
  adopted; neither tier would have changed anything about this pipeline's
  actual constraints (the narration cost problem was solved by the Kokoro
  swap instead, §4 in the 28 Aug document).
- **Full Google OAuth verification (CASA)** for the `youtube.upload`
  restricted scope — considered and explicitly abandoned this session
  (§4e). "In production" publishing status was sufficient to fix the actual
  problem (7-day token expiry) without the disproportionate cost of full
  verification.

---

## 9. Credentials / environment variables / secrets — full current picture

**Automation repo — GitHub Secrets**: `GEMINI_API_KEY`, `PEXELS_API_KEY`,
`PIXABAY_API_KEY`, `JAMENDO_CLIENT_ID`, `GMAIL_ADDRESS`,
`GMAIL_APP_PASSWORD`, **`YOUTUBE_TOKEN_JSON`** (rotated this session — see
§4e; must carry both the upload scope and `yt-analytics.readonly`).
`ELEVENLABS_API_KEY`/`ELEVENLABS_VOICE_ID` present but unused.

**Local `.env` / files**: `credentials.json` (OAuth Desktop app client,
never committed), `token.json` (gitignored, mirrors `YOUTUBE_TOKEN_JSON`).

**cron-job.org job config (external to both repos)**: a fine-grained GitHub
PAT scoped to just `you-never-knew-automation` with Actions: Read and write,
stored only in the cron-job.org job's Authorization header. **No expiry
date recorded — worth checking/setting a reminder to rotate.**

**Google Cloud / Google Auth Platform**: project `you-never-knew-1`.
Publishing status: **In production** (moved from Testing this session, §4e).
User type: External, under the 100-user cap. An "unverified app" warning
screen still appears on manual re-auth — expected, click through via
"Advanced."

**Dashboard repo (Netlify)** — separate secret store: `PEXELS_API_KEY`,
`PIXABAY_API_KEY`, `GITHUB_REPO=Tobifunmi/you-never-knew-automation`.

**Gmail SMTP App Password** — presumably still valid; the connection itself
was timing out locally as of 28 Aug (§6 item 21), status since then unknown.

---

## 10. Daily cadence feasibility (carried over from 28 Aug document, not re-verified)

Pexels ~4.5 calls/video → ~135/month at daily cadence against a 25,000/month
limit. Pixabay has no monthly cap (rolling 60s window only). YouTube Data
API ~1,750 units/video against 10,000/day → ~17.5%/day. Gemini's free tier
nowhere close to constrained at 2-3 calls/day. Jamendo has no published
official quota — the only evidence is empirical; worth watching the
dashboard if failures recur.

---

## 11. Working style / operating principles

Carried forward, reinforced again this session:

- **Verify against actual files/logs/commit history before treating
  something as done or broken.** This session: read `main.py`,
  `engines/youtube.py`, `engines/scheduling.py`, and `config.json` directly
  from the public repo rather than trusting either master prompt's
  description of what scheduling support did or didn't exist — and found
  the 28 Aug document was flatly wrong about it (listed as "not built yet"
  when it was, in fact, live).
- **Don't conflate similar-looking symptoms with the same root cause.**
  This session: the cron-job.org 401 (malformed header) and the later
  `invalid_grant` token expiry were two genuinely separate problems that
  happened to surface back-to-back — treated separately rather than
  assumed to be the same misconfiguration.
- **A push-protection rejection is a save, not an obstacle** — GitHub
  correctly blocked a leaked secret from ever reaching the remote; the
  right response was rewriting local history, not using GitHub's "allow
  this secret" override link.
- **Prefer the proportionate fix over the maximal one.** Moving to "In
  production" publishing status solved the real problem (7-day token
  expiry); pursuing full Google verification would have been substantial
  unnecessary effort for a solo project and was correctly abandoned
  mid-flow.
- **No manual overrides for anything unattended** — the scheduling buffer
  (§4g) exists specifically so a daily cron trigger never depends on a
  human noticing an empty queue in time.
- **Patches (or now, direct guidance) — never assume push access.** This
  assistant gained the ability to *read* the public repo directly this
  session, which is new and worth continuing to use for verification, but
  still cannot write to it.
- **Be honest about documentation gaps rather than papering over them** —
  this document explicitly flags the undocumented scheduling-engine build
  and the undocumented facts-189-to-192 history rather than pretending
  continuity that doesn't exist.

---

## 12. Open items for the next session

1. **cron-job.org PAT expiry** — no expiration date was recorded when it
   was created this session; check it and set a rotation reminder before it
   silently lapses and breaks the daily trigger.
2. **`database/videos.json` / `usage_log.json`** haven't been re-read this
   session — worth doing at the start of any follow-up to get the real
   current fact count, full 189→194 history, and confirm the `kokoro` usage
   count and any other dashboard figures are still behaving as expected.
3. **Gmail SMTP failure notifications** — still unresolved as of 28 Aug,
   not discussed this session. If a pipeline failure happens now (post
   cron-job.org, post scheduling), it's worth confirming whether a failure
   email would actually arrive.
4. **Who/what built the scheduling engine** — not a blocking question, but
   if a future session finds other undocumented changes in the repo, the
   same "verify the live code first" approach that surfaced this one should
   be applied again rather than assuming either master prompt is complete.
5. **Confirm `.gitignore` coverage** is actually correct now (§4f) — worth
   a quick `git status` sanity check on the local machine next time it's
   touched, to make sure `token.json`/`token.json.bak`/`credentials.json`
   are all genuinely ignored and not just missed this time.
