"""
engines/related_video.py

Sets an End Screen element on a just-uploaded YouTube Short, linking it to
the immediately-previous fact's video. No public API exists for End
Screens, so this drives YouTube Studio directly via Playwright, reusing the
session saved by playwright_login.py.

IMPORTANT — READ BEFORE TRUSTING THIS IN CI:
The selectors below are my best-effort guess at Studio's current End Screen
editor, using role/text-based locators (more resilient to minor UI tweaks
than raw CSS, but still real guesses). I have no way to browse Studio
myself to verify them against your actual account. Run this FIRST with
headless=False (see set_related_video_headed() at the bottom) and watch
what happens — if a locator doesn't find its element, Playwright will
raise a clear TimeoutError naming which step failed, which tells us
exactly what to fix. Don't wire this into the unattended --production
pipeline until a headed run has gone all the way through successfully.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

STUDIO_TIMEOUT_MS = 20_000


class RelatedVideoError(Exception):
    pass


def get_previous_fact_video_id(videos_json_path: str, current_fact_number: int) -> str | None:
    """
    Looks up the immediately-previous fact's youtube_id from videos.json.
    Returns None if there's no previous fact recorded (e.g. this is Fact 1)
    or if the previous record has no youtube_id (upload never completed).
    """
    import json

    data = json.loads(Path(videos_json_path).read_text(encoding="utf-8"))
    videos = data.get("videos", [])

    target_number = current_fact_number - 1
    for video in videos:
        if video.get("fact_number") == target_number:
            return video.get("youtube_id")

    return None


def set_end_screen_related_video(
    video_id: str,
    related_video_id: str,
    storage_state_path: str,
    headless: bool = True,
) -> None:
    """
    Opens the Studio editor for `video_id`, adds/updates an End Screen
    element pointing at `related_video_id`, and saves.

    Raises RelatedVideoError with a specific step name if any locator times
    out, so failures are diagnosable rather than a silent no-op.
    """
    if not Path(storage_state_path).exists():
        raise RelatedVideoError(
            f"Session file not found at {storage_state_path}. "
            f"Run playwright_login.py first (or restore it from the GitHub Secret in CI)."
        )

    edit_url = f"https://studio.youtube.com/video/{video_id}/editor"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(storage_state=storage_state_path)
        page = context.new_page()
        page.set_default_timeout(STUDIO_TIMEOUT_MS)

        try:
            page.goto(edit_url)

            # --- Step 1: open the End Screen tab ---
            try:
                page.get_by_role("tab", name="End screen").click()
            except PlaywrightTimeoutError as e:
                raise RelatedVideoError(
                    "Could not find/click the 'End screen' tab. Studio's tab "
                    "label or layout may differ from what's coded here — "
                    "check with headless=False and inspect the actual tab text."
                ) from e

            # --- Step 2: add a "Video" element (as opposed to playlist/subscribe) ---
            try:
                page.get_by_role("button", name="Video").click()
            except PlaywrightTimeoutError as e:
                raise RelatedVideoError(
                    "Could not find/click the 'Video' element-type button on "
                    "the End Screen canvas. Verify this label in a headed run."
                ) from e

            # --- Step 3: choose "Most recent upload" vs "Specific video" ---
            try:
                page.get_by_text("Specific video").click()
            except PlaywrightTimeoutError as e:
                raise RelatedVideoError(
                    "Could not find the 'Specific video' option after adding "
                    "a Video element. Verify in a headed run."
                ) from e

            # --- Step 4: search for the target video by ID/title ---
            try:
                search_box = page.get_by_placeholder("Search for a video")
                search_box.fill(related_video_id)
                page.wait_for_timeout(1500)  # debounce for search results to render
                page.get_by_text(related_video_id, exact=False).first.click()
            except PlaywrightTimeoutError as e:
                raise RelatedVideoError(
                    "Could not search for or select the related video by ID. "
                    "Studio's search may match by title, not raw video ID — "
                    "may need to pass the video's title instead."
                ) from e

            # --- Step 5: save ---
            try:
                page.get_by_role("button", name="Save").click()
                page.wait_for_timeout(2000)
            except PlaywrightTimeoutError as e:
                raise RelatedVideoError("Could not find/click 'Save'.") from e

        finally:
            browser.close()


def set_related_video_headed(video_id: str, related_video_id: str, storage_state_path: str = "storage_state.json"):
    """Convenience wrapper for the required first supervised run (headless=False)."""
    set_end_screen_related_video(video_id, related_video_id, storage_state_path, headless=False)
