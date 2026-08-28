# MASTER CONTINUATION PROMPT — "You Never Knew" Automated YouTube Shorts Factory

Use this as full context in a new conversation. Reflects the actual
verified state of the project as of **28 Aug 2026, later same day**
(a follow-up session on top of the version committed earlier that
day). Several things below were only discovered to be wrong (not just
undone) by reading real files/logs/commit history directly, so treat
this as ground truth over any older summary, including any earlier
version of this same document (an earlier version is committed at
`MASTER_CONTINUATION_PROMPT.md` in the automation repo root — this
document supersedes it; consider re-committing this version over it).

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

**How code changes reach these repos**: this assistant has no push
credentials to either repo. All code changes are delivered as
`git format-patch` files, downloaded from the chat, applied locally via
`git am <file>.patch`, then `git push origin main` by the user. Expect
this pattern to continue in any follow-up conversation.

---

## 1. What this project is

A fully automated production and publishing pipeline for the YouTube
channel **You Never Knew** — "5 Facts You Didn't Know About [Topic]"
YouTube Shorts. Topic selection, script writing, narration, footage,
captions, rendering, background music, metadata, YouTube upload,
playlist assignment, database recording, 48h+ performance tracking, and
failure notification all run on GitHub Actions (when triggered — see
§9 on cron status). Runs locally on Windows for development/testing —
and see §4b for a real, unresolved open question about which mode
recent runs have actually been happening in.

**16 videos successfully produced so far** (`database/videos.json`,
fact numbers 173–188), all currently `unlisted` (test/dev mode — the
channel has not gone to production/public posting yet). **Fact 189
("Bicycles") was attempted this session and failed** at the background-
music stage — see §4c. The topic reservation was released for retry
(the pipeline's normal failure-path behavior), so the next run may
retry "Bicycles" or pick a new topic, depending on what `topic_engine`
does with a released-not-completed topic.

---

## 2. Current status

| Stage | Status |
|---|---|
| YouTube publisher (OAuth, upload, playlists, DB recording) | ✅ Done |
| Narration — Kokoro-82M (local/offline, no API key, no char cap) | ✅ Done — swapped from ElevenLabs |
| Footage (Pixabay → Pexels waterfall) | ✅ Done |
| Captions (local Whisper, burned-in ASS) | ✅ Done |
| Render (FFmpeg, 1080×1920) | ✅ Done |
| Background music (Jamendo, loops short tracks, blocklist-aware) | ⚠️ Works, but see §4c for a real transient failure on Fact 189 and §6 item 20 for a genuine multi-tag-search bug just fixed |
| Topic engine + fact numbering | ✅ Done |
| Autonomous topic/script generation (Gemini) | ✅ Done, audited |
| 48h YouTube Analytics feedback loop (Stage A0, feeds topic selection) | ✅ Done — **gating logic corrected this session, see §4a** |
| Category-guessing fix (WordNet: scans every word, not just the first) | ✅ Done — verified 0/13 fall to default (was 6/13) |
| API usage dashboard: live quotas, call/video correlation, hyperlinks | ✅ Done |
| Kokoro dashboard card (self-tracked "videos narrated" count) | ✅ Code correct — showed 0 due to a timing gap (tracking code landed after the only two Kokoro videos so far were produced), not a bug; will populate on the next successful narration |
| Full unattended automation (GitHub Actions) | ⚠️ Cron set to **daily**, deliberately left commented out — `workflow_dispatch` (manual button) only, until the unpublished-video backlog clears. This is an explicit, repeated choice, not an oversight. |
| Email failure notifications (Gmail SMTP) | ⚠️ **Regressed this session** — see §4c. Previously confirmed working; failed with a local connection timeout on the Fact 189 failure. Not yet diagnosed further. |
| Playlist/record ordering bug | ✅ Fixed (historical) |
| CI secret name mismatch (`TOKEN_JSON` vs `YOUTUBE_TOKEN_JSON`) | ✅ Fixed |
| Persistent Jamendo track blocklist | ✅ Done, in active use, currently tiny (1 track) |
| Shorts "Related video" End Screen | 🔜 Deliberately deferred |
| Google AI Plus/Pro student offer | ℹ️ Researched, concluded **not needed** — see §8b |
| **Local-vs-GitHub-Actions provenance of recent videos** | ❓ Open question, not resolved this session — see §4b |

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
   `youtube_id` that does not yet have a `performance` block, pulls
   cumulative views/likes/comments/averageViewPercentage/
   estimatedMinutesWatched via the **YouTube Analytics API**, writes it
   back into that video's record. Walks the WHOLE list each run. Once
   ≥3 videos have captured performance, `build_performance_context()`
   produces a retention-by-category digest fed into the next step.
   Never raises. Requires the `yt-analytics.readonly` OAuth scope.
   `YouTubePublisher` is instantiated and authenticated at this early
   point specifically so this step can reuse the same OAuth session.

   **Eligibility gating, corrected this session (see §4a for the full
   story):** a video only becomes eligible for the 48h check once
   `analytics.py` has confirmed via the YouTube Data API that its real
   `status.privacyStatus` is `"public"` — not merely that some amount
   of wall-clock time has passed since the pipeline's own upload call
   returned. The 48h window itself is measured from YouTube's own
   `snippet.publishedAt` (the actual go-live moment), cached on the
   record as `live_published_at` the first time a video is confirmed
   public, not from `published_at` (upload-completion time, captured
   by `main.py` immediately after `upload_video()` returns). This
   matters for scheduled uploads — a video can sit private/scheduled
   for well over 48h after upload before real viewers can see it.

   **Still-true zero-view nuance (verified 28 Aug, unchanged by the
   above fix):** a video with genuinely zero real views (unlisted,
   never watched by anyone but the uploader) gets `rows: []` back from
   the Analytics API. The code treats this the same as "not eligible
   yet" — `performance` stays `None`, and the video gets silently
   re-attempted on every subsequent run, indefinitely, harmlessly. This
   is why fact 185 (Neon Signs, 1 self-view) got a captured snapshot
   while fact 186 (Machu Picchu, same age bracket, apparently 0 views)
   still showed `performance: None` after multiple later runs.
   Practical consequence: while the channel stays in unlisted/no-real-
   audience test mode, most videos may never accumulate a captured
   snapshot, which also delays the ≥3-videos threshold for the Gemini
   performance digest ever activating. Should resolve naturally once
   videos go public and get real views.
2. **Stage A/B — Topic + script ingestion.** Manual or autonomous
   (`gemini.get_unique_topic(performance_context=...)` +
   `gemini.generate_script()`). `numbering.get_next_fact_number()`
   assigns the fact number. `topic_engine.reserve_topic()`.
3. **Stage C — Narration.** `engines/kokoro.py :: generate_narration()`
   — see §4 for full detail. Local/offline, no API key. Logs a
   self-tracked "videos narrated" count on success only (no credit
   spent on a failed run, so nothing to log on failure).
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
   fetch/mix → burn in captions. **Background music fetch
   (`music.fetch_and_download_background_track`) can raise
   `MusicError` and abort the whole run here — see §4c for a real
   instance of this on Fact 189.**
9. **Stage G — Metadata.** Title/description/tags, WordNet-based
   playlist categorization — see §7 for the full rewrite detail.
10. **Stage H — Upload.** `unlisted` unless `--production`.
    `published_at` captured immediately after upload
    (`datetime.now(timezone.utc)`, approximated) — this is upload-
    completion time, kept for record-keeping, distinct from
    `live_published_at` (see step 1 above).
11. **Record + complete topic.** Runs immediately after upload
    succeeds, before the playlist step (deliberate, load-bearing
    ordering — see §6 item 1).
12. **Stage I — Playlist.** Isolated `try/except`, never re-raises —
    video is already safely recorded regardless of playlist outcome.
13. **Failure path**: outer `except Exception`. Attempts to send a
    detailed failure email (Gmail SMTP) — **currently unreliable, see
    §4c**. Releases topic reservation only if it was actually reserved.

---

## 4. Narration engine: ElevenLabs → Kokoro-82M (prior session, unchanged)

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

**Real API confirmed by reading the actual installed package**:
`KPipeline(lang_code='a')`, called as `pipeline(text, voice=...,
speed=..., split_pattern='\n+')`, yields a generator of `Result`
objects with `.graphemes`/`.phonemes`/`.audio` (a `torch.FloatTensor`,
converted to numpy before concatenation). Default `split_pattern` is
`r'\n+'`, so `build_narration_text()` deliberately joins hook/fact-
narrations/ending with `\n\n` (not spaces) — chunks generation
naturally at those boundaries rather than sending one long unbroken
block through the model. A small (~250ms, `KOKORO_PAUSE_SECONDS`-
configurable) silence gap is inserted between concatenated chunks so
the stitching doesn't sound abrupt.

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

**Real-world result, confirmed by the user**: ran successfully on the
first real local attempt (`python main.py run`, no `--production`),
completed the full pipeline including a successful `unlisted` upload,
and the user's direct assessment of the narration was **"it sounded
the same."** Multiple further successful narrations since (facts 187,
188, and — up through Stage C — fact 189).

**`elevenlabs.py` was NOT deleted** — kept as a one-import/one-filename
rollback path if Kokoro's quality doesn't hold up at scale. It's also
no longer checked by either usage dashboard.

**Dashboard follow-up**: the ElevenLabs live-quota card was replaced
with a Kokoro card in both `check_usage.py` (local) and
`netlify/functions/usage.js` + `index.html` (live). Kokoro has no
external API/account, so this isn't a live quota check — it just
reads a self-tracked "N videos narrated" count from
`usage_log.json["kokoro"]`, added via a
`usage_tracker.log_call("kokoro", fact_number=...)` call at the end of
`generate_narration()` (success-only).

**Verified timing gotcha (confirmed this follow-up session by reading
actual commit timestamps, not assumed):** the `log_call("kokoro", ...)`
tracking line landed in commit `1184ab6` at **2026-08-28 08:52:10 UTC**
("Update dashboard: swap ElevenLabs card for Kokoro, track narration
count"). Both of the Kokoro videos already produced by that point —
Fact 187 (`published_at` 00:56:57 UTC) and Fact 188 (`published_at`
01:12:33 UTC) — predate that commit. So even though Kokoro narration
had already genuinely succeeded twice, the dashboard correctly showed
"No videos narrated yet" — there was nothing to fix; the count simply
hadn't had a qualifying run yet. **Confirm on the next chat whether a
run since 08:52 UTC has populated the count** (Fact 189's narration
Stage C did complete successfully before the later Jamendo failure —
see §4c — so if `usage_log.json`'s `kokoro` key is still absent after
that, something regressed and is worth investigating fresh, since the
timing excuse no longer applies).

---

## 4a. Analytics 48h-gating fix — THIS session

**The bug.** `analytics.py`'s eligibility check compared `now -
published_at` (upload-completion time, set by `main.py` right after
`upload_video()` returns) against the 48h threshold. For an instant
`public`/`unlisted` upload (the pipeline's only mode today — see §4c
note on scheduling not yet existing) this is effectively identical to
the real go-live time, so it never caused an observed problem yet —
but it would silently start the clock on a scheduled video's upload
time rather than its actual public time, capturing a meaningless
snapshot (or repeatedly attempting a video nobody could watch yet) the
moment scheduling is ever added.

**The fix** (`engines/analytics.py`, delivered as a `git am` patch,
confirmed applied and pushed by the user):
- Before counting a video eligible, `update_performance_log()` now
  calls a new `_get_live_publish_info(youtube, video_id)` helper,
  which queries `youtube.videos().list(part="status,snippet",
  id=video_id)` (the YouTube **Data** API, reusing the same
  `publisher.youtube` client already authenticated for the upload
  scope — no new scope needed).
- If `status.privacyStatus != "public"`, the video is skipped this run
  — genuinely not live yet, regardless of upload age.
- Once confirmed `public`, `snippet.publishedAt` (YouTube's own record
  of the actual go-live moment) is cached on the video's record as a
  new field, `live_published_at`, and used for the 48h window from
  then on. This means the extra Data API read call only happens once
  per video (the first time it's checked after going public) — cheap.
- `published_at` (upload-completion time) is left untouched everywhere
  else in the codebase; only the analytics eligibility check now
  trusts `live_published_at` instead.
- Currently a practical no-op in production (the pipeline has no
  scheduling feature yet — `privacy_status` is only ever `"public"` or
  `"unlisted"`, set immediately at upload), but means the moment
  scheduled publishing IS added, performance tracking will already be
  correct instead of silently wrong.

**Status**: patch applied via `git am` and pushed by the user,
confirmed. Live on `main` as of commit `db1d1af` ("analytics: gate 48h
performance check on actual live-publish time, not upload time").

---

## 4b. Open question: are recent runs actually going through GitHub Actions?

**Not resolved this session — worth settling before trusting the
"unattended automation" story.** `database/videos.json`'s
`narration_path` field reveals which machine actually ran a given
pipeline invocation:
- Facts 178, 179, 180, 184 show real GitHub Actions runner paths
  (`/home/runner/work/you-never-knew-automation/you-never-knew-
  automation/work/Fact_NNN_.../narration.mp3`).
- Facts 181, 182, 183, 185, 186, 187, 188 all show **Windows local
  paths** (`C:\Users\user\Documents\You Never Knew\work\Fact_NNN_...\
  narration.{mp3,wav}`).

Facts 187 and 188 in particular were produced **today** (28 Aug), with
`published_at` timestamps (00:56:57 UTC and 01:12:33 UTC) that line up
closely with a cluster of `usage_log.json` activity across gemini,
pixabay, pexels, youtube_upload, and youtube_analytics — all
consistent with a real, complete pipeline run — but the local Windows
path on both records means that run happened on the user's own
machine (`python main.py run` / `python main.py run --production`
locally), not via the GitHub Actions `workflow_dispatch` button, even
though the user described it in conversation as "one run through
GitHub." Likely explanation: the user ran the pipeline locally and
then manually committed/pushed the updated `database/*.json` files —
which is a legitimate way to work, but is NOT the same thing as
verifying the unattended GitHub Actions path actually works end-to-
end. **Worth explicitly asking, in any follow-up, whether the
`workflow_dispatch` button has ever actually been clicked and
succeeded**, since that's the real prerequisite before ever
uncommenting the daily cron (§10).

---

## 4c. Fact 189 ("Bicycles") — real failed run, THIS session

Full run log (local, `python main.py run`, no `--production`) supplied
by the user:

1. Stage A0 succeeded — captured 48h+ performance for 2 videos (this
   is the corrected live-publish-time logic from §4a working as
   intended, on a local run).
2. Stage A/B succeeded — Gemini picked "Bicycles" as Fact 189's topic,
   topic reserved.
3. Stage C (Kokoro narration) succeeded — 100.67s, 1565 chars. (Per
   §4's open item: check whether this run's `usage_log.json` now has a
   `kokoro` key, since it ran after the 08:52 UTC tracking-code
   commit.)
4. Whisper transcription + timeline: succeeded (no output logged, but
   no failure either).
5. Stage D (footage): succeeded, 5/5 downloaded.
6. Stage E (captions): succeeded.
7. Stage F, background music (`music.fetch_and_download_background_
   track`): **FAILED.** `MusicError: No Jamendo track >= 15.0s found
   for tags 'cinematic+ambient' or fallback 'cinematic' — nothing
   usable even with looping.`
8. Failure-email attempt: **also failed** —
   `notifications: FAILED to send failure email: [WinError 10060] A
   connection attempt failed because the connected party did not
   properly respond after a period of time, or established connection
   failed because connected host has failed to respond.` This is a
   local network/firewall-level SMTP connection timeout (port 465,
   `smtp.gmail.com`), not a code bug — looks like something on the
   user's Windows machine (firewall, ISP, VPN) is currently blocking
   that outbound connection. **Not diagnosed further this session —
   worth checking Windows Defender Firewall / router / ISP port-465
   blocking if this recurs, especially since it means failures during
   unattended runs currently would NOT be reported.**
9. Pipeline correctly released the "Bicycles" topic reservation for
   retry and exited cleanly (no partial/corrupt state left behind —
   the existing failure-path design, from historical bug fix §6 item
   4, worked as intended here).

**Two separate things came out of investigating the Jamendo failure:**

**(a) A genuine, real bug, found and fixed — `VIBE_MAP`'s `+`-joined
tags were being silently mis-encoded.** `engines/music.py`'s
`VIBE_MAP` used a literal `+` as the multi-tag separator (e.g.
`"cinematic+ambient"`), matching Jamendo's documented URL format for
multi-value params. But that string is passed through `requests`'
`params=` dict, which percent-encodes a literal `+` character to
`%2B` (to disambiguate it from an encoded space). Jamendo decodes
`%2B` back to a literal `+` and searches for one tag literally named
`"cinematic+ambient"` — which doesn't exist — instead of the two tags
`cinematic` and `ambient`. Verified directly in a Python REPL:

```python
>>> requests.Request('GET', url, params={'tags': 'cinematic+ambient'}).prepare().url
'...?tags=cinematic%2Bambient'          # broken — one bogus literal tag
>>> requests.Request('GET', url, params={'tags': 'cinematic ambient'}).prepare().url
'...?tags=cinematic+ambient'            # correct — matches Jamendo's own doc examples
```

**Net effect**: every "Tier 1" topic-specific Jamendo search
(`history`, `space`, `science`, `tech`, `nature`, `crime`, and
`default`, all two-word tag combos in `VIBE_MAP`) has been silently
returning zero results since the tag system was introduced — not a
crash, just quietly falling through every single time to the generic
single-tag `"cinematic"` fallback, regardless of the video's actual
topic/vibe. **Fixed**: `VIBE_MAP` values changed from `+`-joined to
space-joined (e.g. `"cinematic ambient"`), which `requests` correctly
encodes to a raw `+` on the wire — exactly the format Jamendo expects.
Delivered as a `git am` patch (commit message: "music: fix Jamendo
multi-tag search silently matching nothing"). **Also documented in
`README.md`'s Known Limitations section** (worth remembering as a
general gotcha for any future multi-value API param, not just this one
call site) and in the `music.py` structure comment in the repo tree.
**Patch delivered; application/push status not yet confirmed by the
user as of this document's writing — verify `git log` on `music.py`
in any follow-up before assuming it's live.**

**(b) Tonight's specific failure is likely NOT explained by (a).** The
fallback tier (`tags="cinematic"`, a single tag, never touched by the
`+`-encoding bug) *also* came back with nothing usable. The blocklist
is tiny (1 track: `jamendo:1073214`, "Audio has copyright claim") —
nowhere near enough to exhaust the top-20-by-popularity result set on
its own. Most likely a one-off Jamendo-side hiccup (rate limit,
transient catalog gap, or bad luck in exactly which 20 tracks came
back) rather than a code bug. **Recommended next step: just retry the
run** — the topic was already released for that. If it fails the same
way again on retry, that would be real signal worth investigating
further (e.g. temporarily logging the raw Jamendo API response body on
a `MusicError`, or checking Jamendo's own status page).

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
│                                    THIS document (from this follow-up
│                                    session) is more current — consider
│                                    re-committing it over the checked-in one
├── .env                           — LOCAL ONLY, gitignored
├── credentials.json               — Google OAuth desktop app credential
├── token.json                     — gitignored, restored from GitHub Secret
│                                    YOUTUBE_TOKEN_JSON in CI
├── database/
│   ├── topics.json
│   ├── videos.json                — 16 successful records (fact 173–188) +
│   │                                 1 failed/released attempt (fact 189,
│   │                                 "Bicycles", not recorded as a video
│   │                                 since it failed before Stage H upload);
│   │                                 includes music_track_id/name,
│   │                                 published_at (upload-completion time),
│   │                                 live_published_at (actual YouTube
│   │                                 go-live time, NEW this session — see
│   │                                 §4a), category, and (once 48h+ past
│   │                                 live_published_at AND actually has
│   │                                 ≥1 real view) performance +
│   │                                 performance_captured_at
│   ├── playlists.json             — legacy, unused
│   ├── usage_log.json             — self-tracked API call counts, COMMITTED
│   │                                 (not gitignored). Keys as of this
│   │                                 session: gemini, jamendo, youtube_upload
│   │                                 + 4 other youtube_* operation keys,
│   │                                 elevenlabs (2 calls, videos [185,186] —
│   │                                 the last two ElevenLabs-narrated videos
│   │                                 before the Kokoro swap), pixabay, pexels,
│   │                                 youtube_analytics. No "kokoro" key
│   │                                 confirmed populated yet as of this
│   │                                 write-up — check on next run (§4).
│   └── music_blocklist.json       — permanent Jamendo track exclusion list,
│                                     in active use, currently 1 entry
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
│   │                                  digest builder — gating logic
│   │                                  corrected THIS session, see §4a
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
│   ├── metadata.py                 — REWRITTEN prior session — see §7
│   ├── music.py                     — Jamendo fetch + mix, usage_tracker +
│   │                                  blocklist wired in; VIBE_MAP tags
│   │                                  fixed THIS session to be space-
│   │                                  separated, not "+"-joined — see §4c
│   ├── notifications.py             — Gmail SMTP failure emails; failing
│   │                                  locally as of THIS session (WinError
│   │                                  10060, connection timeout) — see §4c,
│   │                                  not yet diagnosed further
│   ├── usage_tracker.py             — log_call(service, fact_number=...)
│   └── youtube.py                   — SCOPES includes yt-analytics.readonly;
│                                       credentials exposed for analytics.py
│                                       reuse; publisher.youtube (Data API v3
│                                       client) reused by analytics.py's new
│                                       live-status check (§4a)
├── check_usage.py                  — local dashboard script. Kokoro card
│                                      (not live-checked, self-tracked count
│                                      only) replaces the old ElevenLabs
│                                      live-quota check. Pexels/Pixabay
│                                      checks send a random cache-busting
│                                      query param + Cache-Control: no-cache
│                                      — see §6 item 18.
├── blocklist_track.py              — standalone: blocklist a Jamendo track
├── rerun_footage.py / rerun_footage_wombats.py — standalone historical re-runs
├── playwright_login.py / related_video.py — Related Video prototype, SHELVED
├── README.md                       — kept in sync THIS session too, see §11
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
                                       checkPexels()/checkPixabay() send a
                                       random cache-busting query param +
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

## 6. Bug history — chronological, all fixed/resolved unless noted

*(Items 1–19 preserved from the prior version of this document —
unchanged. Item 20 new this session.)*

1. **Fact 174 near-data-loss bug.** Playlist step used to run before
   `record_video_state()`. Fixed: record+complete-topic now runs
   immediately after upload, before playlist logic.
2. **Narrow exception handling** — broadened to `except Exception`.
3. **Footage failures used `raise SystemExit`** — fixed to
   `raise FootageError`.
4. **Stage A/B sat outside the pipeline's `try` block** — fixed,
   guarded by a `topic_reserved` flag. (Seen working correctly again
   this session on the Fact 189 failure — topic cleanly released.)
5. **Wombats (Fact 174) footage repetition** — pre-`exclude_ids` fix,
   re-run locally.
6. **Pangolins (Fact 175) duplicate/bad-footage uploads** — same root
   cause as #5, resolved.
7. **Jamendo hard duration requirement caused failures** — fixed:
   prefers full-length, falls back to longest ≥15s + loops. (Note:
   this is the "loopable ≥15s" tier logic that Fact 189 still failed
   to clear on BOTH tag tiers — see §4c; not a regression of this fix,
   a separate issue.)
8. **`daily-video.yml`'s cron claimed fixed but wasn't** — verified
   false by reading the real file. **As of the prior session it is
   deliberately commented out again**, by repeated explicit
   instruction. Don't treat either "on" or "off" as permanent without
   re-checking. (Unchanged this session — still commented out. See
   also §4b's open question about whether Actions has ever actually
   run successfully at all.)
9. **`daily-video.yml`'s commit-back step never included
   `usage_log.json`** — fixed, plus the `.gitignore` exclusion reversed.
10. **Dashboard repo folder structure wrong on first deploy** — fixed.
11. **Statue of Liberty (Fact 180) — real YouTube Content ID claim.**
    Resolved manually (re-recorded with different music, re-uploaded).
    Structural fix: `music.py` now records `track_id`/`track_name` per
    video, plus a persistent blocklist.
12. **Jamendo transient failure with misleading error message** —
    fixed: checks `headers.status`, raises Jamendo's real error. (This
    is why Fact 189's failure surfaced as a clear, specific
    `MusicError` rather than a generic/misleading one.)
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
    Pixabay's check too, pre-emptively.
19. **ElevenLabs replaced with Kokoro-82M as the narration engine** —
    see §4 for full detail. Not a "bug" exactly, but listed here for
    chronological completeness since it triggered cascading dashboard
    changes (items above).
20. **NEW — Jamendo `VIBE_MAP` multi-tag searches silently broken by
    `requests`' `+`-encoding behavior, since the tag system was
    introduced.** Full detail in §4c(a). Fixed by switching `VIBE_MAP`
    from `+`-joined to space-joined tag strings. Patch delivered;
    application/push not yet confirmed as of this document.
21. **NEW, UNRESOLVED — Gmail SMTP failure notifications timing out
    locally.** `[WinError 10060]` on the Fact 189 failure — see §4c
    item 8. Not yet diagnosed (likely local firewall/ISP/VPN blocking
    outbound port 465, not a code issue) — flagged for the next
    session, not fixed.

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

**Scheduled/timed YouTube publishing.** Not built yet — `privacy_status`
today is only ever `"public"` or `"unlisted"`, set immediately at
upload, with no `status.publishAt` support in `engines/youtube.py`'s
`upload_video()`. §4a's analytics fix was done proactively so that
whenever this DOES get built, the 48h performance tracking will
already measure from the real go-live time rather than upload time.

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
restored in CI from the **`YOUTUBE_TOKEN_JSON`** GitHub Secret (must
carry BOTH the upload scope AND `yt-analytics.readonly`). No new scope
was needed for §4a's live-status check — it reuses the same Data API
client (`publisher.youtube`) already authenticated for uploads.

**Dashboard repo (Netlify)** — separate store: `PEXELS_API_KEY`,
`PIXABAY_API_KEY`, `GITHUB_REPO=Tobifunmi/you-never-knew-automation`.
`ELEVENLABS_API_KEY` still present but unused. When rotating any key,
paste carefully — a copy-paste whitespace issue caused a real,
hard-to-diagnose 401 earlier (see §6 item 16) before the ElevenLabs
check was removed entirely.

**Gmail SMTP App Password** — presumably still valid (unchanged this
session), but the connection itself is currently timing out locally
(§6 item 21) — worth checking this credential is still valid too, once
the network-level issue is ruled out or fixed, just to be thorough.

---

## 10. `daily-video.yml` — current real state (verified, not assumed)

```yaml
on:
  #schedule:
  #- cron: '0 10 * * *'  # Every day at 10:00 UTC

  # Manual trigger button in GitHub Actions UI
  workflow_dispatch:
```

**Deliberately commented out**, by explicit repeated instruction: "I'll
change the cron to daily, but still keep it commented out until I'm
ready. I still have unpublished videos for now." Do not enable without
being asked. Only `workflow_dispatch` currently triggers a run — and
per §4b, it's not even confirmed that button has been successfully
clicked recently; the most recent videos' `narration_path` values
point to local runs instead.

Steps, in order: checkout → setup Python 3.11 → install ffmpeg AND
espeak-ng (single combined step) → install pip deps → cache Hugging
Face model weights (`actions/cache`, path `~/.cache/huggingface`,
keyed on `hashFiles('requirements.txt')`) → download WordNet corpus →
restore `topics.json`/`videos.json`/`token.json` from Secrets → run
`python main.py run --production` with secrets injected as env vars
(no longer includes ELEVENLABS_API_KEY/ELEVENLABS_VOICE_ID) →
commit-back step (`if: always()`) — `git add database/topics.json
database/videos.json database/usage_log.json`, commit, push, all with
`|| true`.

**Daily-cadence feasibility check performed previously** (before the
schedule was changed from Mon/Thu to daily): Pexels ~4.5 calls/video →
~135/month at daily cadence against a 25,000/month limit, trivial.
Pixabay has no monthly cap (rolling 60s window only). YouTube Data API
~1,750 units/video against 10,000/day budget → ~17.5%/day, comfortable.
Gemini's request-based free tier is nowhere close to being a
constraint at 2-3 calls/day. **Jamendo is the one honest asterisk**: no
published official quota exists; the only evidence is empirical.
**Fact 189's failure this session is a small additional data point
here** — not proof of a quota problem (more likely a one-off
catalog/rate hiccup per §4c(b)), but worth folding into the "watch the
dashboard closely for the first couple of weeks after cron is ever
actually enabled" plan.

---

## 11. Documentation state

`README.md` in the automation repo has been kept current across
multiple sessions — most recently (THIS session) updated to add: the
live-publish-time analytics gating explanation (§4a) in the Analytics
Feedback Loop section and the `videos.json` field list, and the
Jamendo `+`-encoding bug + fix (§4c(a)) in the `music.py` structure
comment and a new Known Limitations entry. Delivered as a `git am`
patch; **application/push status not yet confirmed by the user** as of
this document's writing.

**A committed copy of an earlier version of this exact document**
lives at `/MASTER_CONTINUATION_PROMPT.md` in the automation repo root
(added by the user, not automatically kept in sync). It predates this
entire follow-up session's work (§4a, §4c, README updates) — this
document is the current one; consider replacing the committed file
with this version so the repo's own copy doesn't mislead a future
session that reads it directly instead of being handed this prompt.

---

## 12. Working style / operating principles

Each of these has concretely prevented or caught a real problem in
this project's actual history:

- **Verify against actual files/logs/commit history before treating
  something as done OR as broken.** Recurred twice more this session:
  the Kokoro-dashboard-still-showing-zero question was answered by
  reading real commit timestamps (`git log`) and comparing them
  against `published_at` on the actual video records — not assumed to
  be a bug. Conversely, the Jamendo `+`-encoding issue was confirmed
  as a REAL bug by actually running `requests.Request(...).prepare().url`
  locally and observing the mis-encoding directly, not by pattern-
  matching the error message to a guess.
- **Don't conflate similar-looking symptoms with the same root
  cause.** Recurred again this session: Fact 189's Jamendo failure
  produced two candidate explanations (the `+`-encoding bug, and a
  possible transient Jamendo-side issue) that were kept explicitly
  separate rather than assumed to be one and the same — the encoding
  bug explains why Tier 1 always fails, but does NOT by itself explain
  why the Tier 2 fallback (unaffected by that bug) also failed
  tonight.
- **No manual overrides for anything unattended.** Fixes are either
  genuinely automated or explicitly flagged as needing a one-time
  human step (Playwright login, a fresh OAuth re-auth for a new scope,
  installing `espeak-ng` locally) — never a silent assumption someone
  will intervene during a scheduled run.
- **Prefer free/offline over paid/AI where genuinely sufficient** —
  established via the Kokoro swap, WordNet-over-AI-classification, and
  SMTP-over-OAuth precedents.
- **Be honest about what was and wasn't actually verified**, including
  patch application status: this document explicitly distinguishes
  "patch delivered" from "confirmed applied and pushed" for each of
  this session's three changes (analytics.py — confirmed; music.py —
  not yet confirmed; README.md — not yet confirmed) rather than
  assuming success.
- **Isolate failure domains.** A failure in one stage should never
  retroactively invalidate work that already genuinely succeeded —
  Fact 189's Kokoro narration, footage, and captions all genuinely
  completed before the music-stage failure, and nothing about that
  failure calls those earlier stages into question.
- **Accept known, narrow, low-probability limitations rather than
  over-engineering fixes** — but always name them explicitly (§7 fix
  detail, §3 step 1's zero-view analytics nuance, §10's Jamendo
  asterisk, §4c(b)'s "probably transient, retry first" call).
- **When infrastructure changes what's true, go back and fix the
  earlier advice that's now wrong** — done again this session:
  updating the README's Analytics section and field list now that
  `live_published_at` exists, rather than leaving the old
  `published_at`-only description silently stale.
- **Patches, not direct pushes, from this assistant.** No push
  credentials to either repo — all code changes are delivered as `git
  format-patch` files, applied locally via `git am <file>.patch` then
  `git push origin main` by the user. Expect this pattern to continue.

---

## 13. Immediate open items for the next conversation

In rough priority order:

1. **Confirm the two pending patches (music.py's Jamendo fix, and the
   README update) were actually applied via `git am` and pushed.** The
   analytics.py patch (§4a) was confirmed; these two were not, as of
   this document.
2. **Retry Fact 189 ("Bicycles")** — topic was released, should be
   pickable again on the next run. Watch whether the Jamendo failure
   recurs; if it does, that upgrades from "probably transient" to
   "worth real investigation" (§4c(b)).
3. **Diagnose the Gmail SMTP `WinError 10060`** (§6 item 21, §4c item
   8) — currently unreported failures during unattended runs is a real
   gap, especially relevant before ever enabling the daily cron.
4. **Settle the local-vs-Actions provenance question (§4b)** — has
   `workflow_dispatch` actually been run successfully recently? Worth
   doing one explicit, watched Actions run and checking the resulting
   `narration_path` to confirm.
5. **Check whether `usage_log.json` now has a `kokoro` key** after
   Fact 189's narration (which ran after the tracking code landed) —
   confirms the dashboard will populate correctly, or reveals a fresh
   regression if it's still empty.
6. Once 1–4 are settled, re-evaluate whether the unpublished-video
   backlog has cleared enough to reconsider uncommenting the daily
   cron (still an explicit "not yet" as of this document).