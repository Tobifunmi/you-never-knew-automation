"""
engines/notifications.py

Sends a detailed failure email via Gmail SMTP (App Password auth, not
OAuth — no extra token file to manage, consistent with keeping this
pipeline's credential surface as small as possible).

Setup (one-time):
  1. Enable 2-Step Verification on the Gmail account, if not already on
     (required before Google will issue App Passwords).
  2. Generate an App Password: Google Account -> Security -> 2-Step
     Verification -> App passwords. Name it something like "you-never-knew".
  3. Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env locally, and as
     GitHub Secrets for CI (same restore-from-secret pattern as your other
     credentials).

This module never raises on its own send failure — if the email itself
can't be sent (bad creds, network issue, whatever), it prints the error to
stdout and returns False, so a notification failure can never mask or
replace the actual pipeline failure that triggered it. The caller is
expected to re-raise the original exception regardless of what this
returns.
"""

from __future__ import annotations

import os
import smtplib
import traceback
from datetime import datetime, timezone
from email.mime.text import MIMEText

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def _actions_run_url() -> str | None:
    """Builds a link to the current GitHub Actions run, if running in CI."""
    server = os.environ.get("GITHUB_SERVER_URL")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server and repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return None


def send_failure_email(
    stage: str,
    error: Exception,
    fact_number: int | None = None,
    topic: str | None = None,
    production: bool = False,
    to_address: str | None = None,
) -> bool:
    """
    Sends a failure notification email with stage, topic/fact context,
    the exception, and a full traceback.

    Returns True if the email was sent, False otherwise (never raises).
    """
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not gmail_address or not app_password:
        print("notifications: GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set, skipping failure email.")
        return False

    to_address = to_address or gmail_address

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    run_url = _actions_run_url()
    tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))

    subject = f"[You Never Knew] Pipeline FAILED at: {stage}"
    if fact_number:
        subject += f" (Fact {fact_number})"

    body_lines = [
        f"Stage failed:     {stage}",
        f"Time:             {timestamp}",
        f"Mode:             {'production' if production else 'test/unlisted'}",
        f"Fact number:      {fact_number if fact_number is not None else '(not yet assigned)'}",
        f"Topic:            {topic or '(unknown)'}",
        f"Error type:       {type(error).__name__}",
        f"Error message:    {error}",
        "",
        "Actions run:      " + (run_url or "(not running in GitHub Actions)"),
        "",
        "--- Full traceback ---",
        tb,
    ]
    body = "\n".join(body_lines)

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = to_address

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(gmail_address, app_password)
            server.sendmail(gmail_address, [to_address], msg.as_string())
        print(f"notifications: failure email sent to {to_address}.")
        return True
    except Exception as send_error:
        print(f"notifications: FAILED to send failure email: {send_error}")
        return False


if __name__ == "__main__":
    # Self-test: run this file directly to confirm your Gmail App Password
    # setup actually works, before wiring it into main.py.
    #
    #   python engines/notifications.py
    #
    print("Sending a test failure email...")
    fake_error = RuntimeError("This is a test error from notifications.py's self-test.")
    try:
        raise fake_error
    except RuntimeError as e:
        sent = send_failure_email(
            stage="Self-test (not a real pipeline run)",
            error=e,
            fact_number=999,
            topic="Test Topic",
            production=False,
        )
    print("Sent successfully." if sent else "Send failed — check the error above and your .env values.")
