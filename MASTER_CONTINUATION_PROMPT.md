# MASTER CONTINUATION PROMPT — "You Never Knew" Automated YouTube Shorts Factory

Use this as full context in a new conversation. Reflects the verified state of
the project as of **25 Sep 2026**. This version supersedes the previous
`MASTER_CONTINUATION_PROMPT.md` (dated 20 Sep 2026, committed in the automation
repo root) — that document is now out of date in the ways described below.
Consider re-committing this version over it.

**Repo-read-access gap, updated (25 Sep)**: the 20 Sep document reported that
direct repo read access did not work and every fix that session was based on
pasted files. That has now changed — `git clone` of the public repo via the
sandbox's `bash_tool` (over `https://github.com/...`, `github.com` is an
allowed domain) **worked cleanly this session**, giving direct read access to
every file without Tobi needing to paste them. This does not extend to
`web_fetch` of raw GitHub URLs, which is still constrained to URLs that
already appeared in a prior search/fetch result. **Push access is still
unavailable** — no credentials — so code changes this session were still
delivered as full replacement file contents for Tobi to add/commit/push
manually (a GitHub token exchange was offered to enable a direct push, but
Tobi opted to take the file and apply it himself instead). Next session:
confirm `git clone` read access again before assuming it's reliable
long-term, but default to attempting it before asking Tobi to paste files.

GitHub username: **Tobifunmi** (capitalized). Automation repo:
`github.com/Tobifunmi/you-never-knew-automation` (public). Dashboard repo:
`github.com/Tobifunmi/you-never-knew-dashboard` (public). Live dashboard:
`https://you-never-knew.netlify.app/`.

Local dev machine: Windows 10/11, PowerShell, two separate local repo folders
— `C:\Users\user\Documents\You Never Knew` (automation) and
`C:\Users\user\Documents\You Never Knew - Dashboard` (dashboard).

**How code changes reach the repo**: this assistant has no push credentials.
Changes are delivered as full replacement file contents (or, where useful,
`git format-patch`-style diffs) for Tobi to save, commit, and push locally —
see the gap note above for why "read the repo directly first" can't be relied
on this session. Still no write/push access.

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

**As of 20 Sep 2026 (verified via YouTube Studio screenshots)**: the channel
is live and posting publicly on a real daily cadence, now well past fact 194.
Most recently confirmed state:
- Fact 200 ("Vending Machines") — public, published Sep 20, 58+ views
- Fact 199 ("Matches") — public, published Sep 19, 59+ views
- Fact 198 ("Mirrors") — public, published Sep 18, 158 views
- Fact 197 ("Tardigrades") — public, published Sep 17, 5 views
- Fact 196 ("Rogue Waves") — public, published Sep 16, 1,233 views
- Fact 195 ("Sinkholes") — public, published Sep 15, 1,106 views
- Fact 201 ("Traffic Lights") — **scheduled**, Sep 21 12:00am Lagos
  (`2026-09-20T23:00:00Z`) — see §4h, this is a manually-reuploaded
  replacement video after the original was copyright-flagged
- Fact 202 ("Barcodes") — **scheduled**, Sep 22, still processing to HD at
  time of screenshot — first video scheduled by the pipeline after §4h's fix

The full history of facts 189–194 (the transition documented in the 12 Sep
version of this file) is unchanged from that document. `database/videos.json`
and `usage_log.json` in the repo remain the source of truth for anything
beyond what's summarized here.

---

## 2. Current status

| Stage | Status |
|---|---|
| YouTube publisher (OAuth, upload, scheduling, playlists, DB recording) | ✅ Done, live in production |
| Scheduling (`engines/scheduling.py`, real `status.publishAt`) | ✅ Done, live — see §4g. Maintains a rolling one-video-ahead buffer: each run schedules the next video `cadence_hours` (24h) after the latest scheduled/live video's real anchor time on YouTube, cross-checked against local DB to catch drift |
| Scheduling error-handling split (`SchedulingDriftError` vs `SchedulingStatusCheckError`) | ✅ Done this session — see §4h |
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
| Email failure notifications (Gmail SMTP) | ✅ Confirmed working this session — the original Stage H `SchedulingDriftError` failure email is what alerted Tobi to the fact 201 incident (§4h) in the first place. Prior `WinError 10060` concern appears resolved/moot. |
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
   confirms it has no record of it at all, raises `SchedulingDriftError`
   rather than silently guessing. **As of §4h (this session)**: if the
   status-check call itself fails (auth/quota/network — an `HttpError`),
   `get_video_status()` now raises `VideoStatusCheckError` instead of
   silently returning `None`, and `compute_next_publish_at()` re-raises
   that as `SchedulingStatusCheckError` — kept distinct from
   `SchedulingDriftError` so a failure email says which situation
   happened without anyone having to dig through the traceback.
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

### 4h. Fact 201 copyright flag + scheduling error-handling fix (this session, 20 Sep 2026)

**Trigger**: Actions run #24 (`35474877075`, manually triggered 23:00 UTC)
failed at Stage H on fact 202 ("Barcodes") with:

```
SchedulingDriftError: Fact 201 (youtube_id=ZusD4oFWtXQ) is in the local
database but YouTube has no record of it (or the status check failed).
```

**Root cause, confirmed by Tobi**: fact 201's video ("Traffic Lights") had
been copyright-flagged and removed by YouTube. This is a recurring recovery
pattern for this channel: YouTube emails Tobi on a flag, he downloads the
flagged video, swaps the background music, and reuploads — which produces a
**new video ID**, breaking the local DB's `youtube_id` reference for that
fact and tripping `SchedulingDriftError` on the next scheduling run. This is
not a code bug; it's a real gap between "video replaced out-of-band" and
"the database that assumes only the pipeline itself uploads things."

**Immediate fix (manual DB correction)**: after Tobi reuploaded and
rescheduled fact 201 for Sep 21 12:00am Lagos (`2026-09-20T23:00:00Z`) and
re-added it to its playlist in Studio, fact 201's `database/videos.json`
record was hand-corrected:
- `youtube_id`: `ZusD4oFWtXQ` → `48AfQX9VBIU`
- `state`: `"playlist_added"` → `"scheduled"` (the reupload went through
  Studio, not the pipeline's own Stage I, so a pipeline-completion state
  was inaccurate)
- `published_at`: the stale Sep 18 timestamp (from the deleted video) →
  `null` (not live yet)
- `scheduled_publish_at`: left as `2026-09-20T23:00:00Z`, confirmed against
  the real Studio-scheduled time

Committed and pushed; the next run succeeded — fact 202 scheduled cleanly
for `2026-09-21T23:00:00Z` (Sep 22), matching the cadence math exactly and
confirming the anchor logic works correctly once the local record is
accurate.

**Structural fix (code change, applied this session)**: `get_video_status()`
in `engines/youtube.py` was catching every `HttpError` and returning `None`
either way, so `compute_next_publish_at()` couldn't tell "YouTube confirms
this video doesn't exist" apart from "the API call itself broke" (auth
expiry, quota exhaustion, a transient 5xx) — both produced the exact same
`SchedulingDriftError`, which is why this incident needed manual digging to
diagnose instead of being self-evident from the failure email. Fixed:
- `engines/youtube.py`: new `VideoStatusCheckError` exception.
  `get_video_status()` now returns `None` **only** on a genuine
  confirmed-absent response (a 200 with empty `items`); any `HttpError`
  during the call is re-raised as `VideoStatusCheckError` instead of
  silently swallowed and logged via `print()`.
- `engines/scheduling.py`: new `SchedulingStatusCheckError` exception,
  imported alongside `VideoStatusCheckError` from `.youtube`.
  `compute_next_publish_at()` catches `VideoStatusCheckError` and re-raises
  it as `SchedulingStatusCheckError`; `SchedulingDriftError` now means
  exclusively "YouTube positively confirmed something is wrong" (video
  missing, or a real `publishAt` mismatch).

Both updated files were produced as full replacement content (not a
`git am` patch — see the repo-read-access gap noted at the top of this
document) for Tobi to save, commit, and push locally. **Not yet
independently re-verified against the live repo** — confirm on next
session that both files actually landed on `main` as intended.

**Decision made**: no separate daily sanity-sweep workflow for
proactively catching flagged/removed videos. YouTube's own copyright-flag
email already provides that alert, and Gmail delivery of the pipeline's own
failure emails is now confirmed working (this incident is the proof — see
the status table above). The existing "run fails loudly with a distinct
error → check email → fix the DB record" loop is considered sufficient;
building a redundant sweep was explicitly declined as unnecessary.

---

### 4i. Gemini 503 pattern and retry backoff hardening (25 Sep)

Three separate `GeminiError: Gemini call failed after 3 attempts: 503
UNAVAILABLE` failures at Stage A/B (topic ingestion) in five days —
14 Sep, 19 Sep, and 24 Sep. All three exhausted the old 3-retry/short-sleep
loop in `engines/gemini.py :: _call_gemini()` before giving up.

**Diagnosis**: not an account-specific or code-level problem. A web search
this session found active, ongoing reports on Google's own developer
forums of exactly this "high demand" 503 across Gemini 2.5/3.x models,
some spanning weeks, with occasional Google-staff acknowledgment of an
issue on their side — while the public status page shows all-green
through it. Treated as a known external reliability gap to harden against,
not something fixable by changing how the topic/script prompts are built.

**Fix applied**: `_call_gemini()`'s retry backoff changed from
`time.sleep(2 * attempt)` (2s, then 4s — exhausted in ~6 seconds total) to
a flat `time.sleep(300)` (5 minutes) between every attempt, with a `print()`
log line on each wait so it's visible in Actions logs. `max_retries` left
at 3, so worst case is now ~10 minutes before Stage A/B gives up entirely,
versus ~6 seconds before. This backoff is shared by both
`generate_candidate_topic()` (topic gen) and `generate_script()` (script
gen), since both route through `_call_gemini()`.

Delivered as a full replacement `engines/gemini.py` for Tobi to add and
commit himself (see the repo-read-access note at the top of this document —
push access still isn't available). **Not yet independently re-verified
against the live repo** — confirm on next session that the flat 5-minute
backoff actually landed on `main`.

**Deferred, not built this session**: a fallback model (e.g. dropping to a
lighter Gemini model on repeated 503s) and not letting a Stage A/B failure
silently cost a scheduled publish slot (currently: run fails, cron-job.org's
trigger for that slot is simply missed, and recovery is manual/noticed via
the failure email). Both flagged as open items — see §12.

---

## 5. Repo structure — `you-never-knew-automation`

Reflects the live repo as read directly during the 12 Sep session (`main.py`,
`engines/youtube.py`, `engines/scheduling.py`, `config.json` verified
firsthand then). Not independently re-verified this session — see the
repo-read-access gap noted at the top of this document. `engines/youtube.py`
and `engines/scheduling.py`'s entries below reflect the §4h changes as
written and handed to Tobi, not as re-confirmed live in the repo. The rest
carried over from the 28 Aug document and never independently verified at
all — flagged accordingly.

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
│   ├── gemini.py                    — _call_gemini() retries 3x, flat
│   │                                  5-min wait between attempts (was
│   │                                  2s/4s), §4i
│   ├── analytics.py                — 48h gating on live_published_at, §4a
│   ├── scheduling.py                — verified live 12 Sep, updated §4h
│   │                                  this session (not independently
│   │                                  re-verified — see repo-read gap).
│   │                                  compute_next_publish_at(),
│   │                                  SchedulingDriftError (YouTube
│   │                                  confirmed something's wrong),
│   │                                  SchedulingStatusCheckError (the
│   │                                  status-check call itself failed —
│   │                                  new, §4h).
│   ├── kokoro.py                   — current narration engine
│   ├── elevenlabs.py                — previous engine, kept as rollback,
│                                     unused
│   ├── captions.py
│   ├── timeline.py
│   ├── footage.py
│   ├── renderer.py
│   ├── metadata.py                 — WordNet category-guessing fix, §6/§7
│   ├── music.py                     — Jamendo, VIBE_MAP fix §4c/§6 item 20
│   ├── notifications.py             — Gmail SMTP failure emails; confirmed
│                                     working this session (§4h) — prior
│                                     WinError 10060 concern appears
│                                     resolved/moot
│   ├── usage_tracker.py
│   └── youtube.py                   — verified live 12 Sep, updated §4h
│                                     this session (not independently
│                                     re-verified — see repo-read gap).
│                                     SCOPES = [youtube, yt-analytics.readonly].
│                                     upload_video(..., publish_at=None) —
│                                     passing publish_at forces
│                                     privacyStatus="private" regardless of
│                                     the privacy_status arg (YouTube
│                                     requirement). get_video_status(video_id)
│                                     — real Data API status+snippet lookup,
│                                     used by scheduling.py; now returns
│                                     None ONLY on confirmed-absent, raises
│                                     new VideoStatusCheckError if the API
│                                     call itself fails (§4h).
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
25. **NEW, 25 Sep session** — Gemini 503 UNAVAILABLE hit Stage A/B three
    times in five days, exhausting the old fast retry loop (~6s total).
    Diagnosed as a known, ongoing Gemini-side reliability issue (not
    account/code-specific — confirmed via Google developer forum reports).
    Hardened, not "fixed" (the underlying 503s are outside this repo's
    control): `_call_gemini()`'s backoff changed to a flat 5-minute wait
    between attempts. Full detail §4i.

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

**Gmail SMTP App Password** — confirmed working this session (§4h): the
Stage H failure email for fact 202's `SchedulingDriftError` is what surfaced
the fact 201 incident. The `WinError 10060` local timeout noted as of 28 Aug
appears resolved or was never a factor for the Actions-run path specifically.

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
- **Patches (or direct guidance) — never assume push access.** Still no
  write access as of 20 Sep. The 12 Sep session's direct-repo-read ability
  did NOT reproducibly work in the 20 Sep session (see the gap note at the
  top of this document) — don't assume it works without re-confirming;
  default to asking for pasted file contents.
- **Be honest about documentation gaps rather than papering over them** —
  this document explicitly flags the undocumented scheduling-engine build,
  the undocumented facts-189-to-192 history, and (new, 20 Sep) the
  repo-read-access regression, rather than pretending continuity that
  doesn't exist.

**Added 20 Sep session:**

- **Distinguish "confirmed wrong" from "couldn't check" in error types,
  not just in prose.** §4h's `SchedulingStatusCheckError` split exists
  because the original `SchedulingDriftError` conflated a positively
  confirmed problem (video removed) with an uncertain one (API call
  failed) — the fix was a new exception class, not a better log message,
  so the distinction survives into whatever reads the failure email.
- **A working failure-notification path is worth confirming, not just
  building once.** This session's Gmail SMTP email (§4h) is what turned an
  otherwise-silent copyright removal into something caught the same day —
  validates why §12's now-closed "confirm failure email arrives" item
  mattered.
- **When manual, out-of-band recovery is a known recurring pattern (Tobi's
  download → swap music → reupload flow), document the DB-record-repair
  steps as a runbook** (README's new "Recovering from a flagged/removed
  video" section) rather than re-deriving them from scratch next time it
  happens.

---

## 12. Open items for the next session

**Carried over, still open:**

1. **cron-job.org PAT expiry** — still no expiration date recorded; check it
   and set a rotation reminder before it silently lapses and breaks the
   daily trigger.
2. **`database/videos.json` / `usage_log.json`** — spot-checked this session
   only for facts 195–202 via §4h; a full re-read for the complete
   189→202 history and `kokoro`/other usage-log figures still hasn't
   happened.
3. **Who/what built the scheduling engine** — still unresolved, still not
   blocking. If a future session finds other undocumented changes, apply
   the same "verify real files before trusting a description" approach.
4. **Confirm `.gitignore` coverage** (§4f) — still not re-checked with a
   fresh `git status` on the local machine.

**Resolved this session (20 Sep):**

- ~~Gmail SMTP failure notifications~~ — confirmed working, §4h.

**Resolved this session (25 Sep):**

- ~~Re-attempt direct repo read access~~ — `git clone` via `bash_tool`
  worked cleanly this session; see the updated gap note at the top of this
  document. Confirmed `git clone` access is usable going forward (pending
  re-confirmation next session), though push access still isn't.
- ~~Confirm §4h's two file replacements actually landed on `main`~~ —
  since read access now works, this can be (and should be) directly
  re-checked at the start of next session by cloning the repo and reading
  `engines/youtube.py` / `engines/scheduling.py`, rather than staying an
  open item indefinitely.

**New this session (25 Sep):**

5. **Confirm the `engines/gemini.py` backoff change (§4i) actually landed
   on `main`.** Delivered as a full replacement file for Tobi to add and
   commit himself (push access still unavailable) — verify by cloning the
   repo and checking `_call_gemini()` uses `time.sleep(300)`.
6. **Watch whether the 5-minute backoff actually reduces Gemini 503
   failures**, or whether the underlying demand-spike issue is frequent/
   long enough that even a 10-minute total retry window isn't sufficient —
   if 503s keep recurring, the deferred fallback-model and
   don't-silently-miss-a-publish-slot ideas from §4i should get built.
7. **`README.md`'s new "Recovering from a flagged/removed video" section
   and the updated Scheduling/error-handling sections** (written 20 Sep) —
   still not independently re-verified as pushed; check alongside item 5.
- **Watch for a repeat copyright flag.** One flagged video (fact 201,
  "Traffic Lights") isn't necessarily a pattern, but if it happens again,
  worth checking whether it's tied to a specific Jamendo track, a specific
  Pixabay/Pexels clip, or something about the topic itself, rather than
  treating each one as an isolated fluke.
