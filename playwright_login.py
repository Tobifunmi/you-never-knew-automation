"""
ONE-TIME setup script. Run this locally, interactively, whenever the saved
session expires or before the very first automated related-video run.

Opens a real (visible) browser, lets you log into your Google account and
YouTube Studio manually (handles 2FA/captchas/whatever Google throws at
you), then saves the authenticated session to storage_state.json.

That file is what gets restored from a GitHub Secret for headless CI runs
later — same bootstrap-once-then-reuse pattern as token.json for the
YouTube Data API OAuth flow.

Usage:
    python playwright_login.py

Then base64-encode storage_state.json and store it as a GitHub Secret
(e.g. YT_STUDIO_SESSION) so the workflow can restore it — same as TOKEN_JSON.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright

STORAGE_STATE_PATH = "storage_state.json"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://studio.youtube.com")

        print("\n" + "=" * 70)
        print("A browser window has opened. Log into your Google account")
        print("and get to the YouTube Studio dashboard (handle any 2FA).")
        print("Once you can see your channel's Studio dashboard, come back")
        print("here and press Enter.")
        print("=" * 70 + "\n")
        input("Press Enter once you're logged in and on the Studio dashboard...")

        context.storage_state(path=STORAGE_STATE_PATH)
        print(f"\nSession saved to {Path(STORAGE_STATE_PATH).resolve()}")
        print("Next steps:")
        print("  1. base64-encode this file")
        print("  2. Store it as a GitHub Secret (e.g. YT_STUDIO_SESSION)")
        print("  3. Add a restore step in daily-video.yml, same pattern as TOKEN_JSON")

        browser.close()


if __name__ == "__main__":
    main()
