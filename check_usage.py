"""
check_usage.py — one-command view of API usage/credits across every
service this pipeline uses.

Run with:
    python check_usage.py

Prints a console report AND writes usage_dashboard.html (open it in a
browser, re-run this script any time to refresh it — it's a static
snapshot, not a live-updating page).

WHAT'S ACTUALLY LIVE vs. WHAT'S NOT:

  ElevenLabs — LIVE. Real GET /v1/user/subscription call, exact
    character_count / character_limit / reset date.

  Pexels — LIVE. Rate-limit headers (X-Ratelimit-*) come back on every
    successful response, so this makes one cheap throwaway search request
    just to read them. This is your MONTHLY quota (20,000/mo default).

  Pixabay — LIVE, but it's a rolling rate limit (100 requests/60s), not a
    monthly credit balance — so "remaining" here just means "right now",
    not "this month."

  Jamendo — NOT LIVE. No public endpoint exposes remaining quota for a
    client_id. Shows your locally self-tracked call count (see
    engines/usage_tracker.py) if you've wired that in, otherwise just a
    link to check manually.

  Gemini / YouTube Data API — NOT LIVE for the same reason as Jamendo,
    PLUS actually querying these programmatically would require adding a
    separate Google Cloud Monitoring OAuth scope/credential just for this
    dashboard — not worth the extra credential surface for a usage
    number. Shows self-tracked local counts if available, otherwise links
    to the real dashboards.

Local self-tracked counts (Jamendo/Gemini/YouTube) only exist if
engines/usage_tracker.py has actually been wired into those engine files
to log each call — this script reads whatever's there, it doesn't
generate the counts itself.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

USAGE_LOG_PATH = Path("database/usage_log.json")


def _fmt_unix(ts) -> str:
    if not ts:
        return "unknown"
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def check_elevenlabs() -> dict:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        return {"service": "ElevenLabs", "status": "no API key set", "live": False}

    try:
        resp = requests.get(
            "https://api.elevenlabs.io/v1/user/subscription",
            headers={"xi-api-key": api_key},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        used = data.get("character_count", 0)
        limit = data.get("character_limit", 0)
        pct = (used / limit * 100) if limit else 0
        return {
            "service": "ElevenLabs",
            "live": True,
            "used": used,
            "limit": limit,
            "pct": round(pct, 1),
            "resets": _fmt_unix(data.get("next_character_count_reset_unix")),
            "tier": data.get("tier"),
        }
    except Exception as e:
        return {"service": "ElevenLabs", "status": f"error: {e}", "live": False}


def check_pexels() -> dict:
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        return {"service": "Pexels", "status": "no API key set", "live": False}

    try:
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": api_key},
            params={"query": "nature", "per_page": 1},
            timeout=15,
        )
        resp.raise_for_status()
        limit = resp.headers.get("X-Ratelimit-Limit")
        remaining = resp.headers.get("X-Ratelimit-Remaining")
        reset = resp.headers.get("X-Ratelimit-Reset")
        if limit is None or remaining is None:
            return {"service": "Pexels", "status": "call succeeded but no rate-limit headers returned", "live": False}
        used = int(limit) - int(remaining)
        pct = (used / int(limit) * 100) if int(limit) else 0
        return {
            "service": "Pexels",
            "live": True,
            "used": used,
            "limit": int(limit),
            "pct": round(pct, 1),
            "resets": _fmt_unix(reset),
        }
    except Exception as e:
        return {"service": "Pexels", "status": f"error: {e}", "live": False}


def check_pixabay() -> dict:
    api_key = os.environ.get("PIXABAY_API_KEY")
    if not api_key:
        return {"service": "Pixabay", "status": "no API key set", "live": False}

    try:
        resp = requests.get(
            "https://pixabay.com/api/videos/",
            params={"key": api_key, "q": "nature", "per_page": 3},
            timeout=15,
        )
        resp.raise_for_status()
        # Pixabay's exact header names aren't consistently documented publicly;
        # check the common conventions defensively rather than assume one.
        limit = resp.headers.get("X-RateLimit-Limit") or resp.headers.get("X-Ratelimit-Limit")
        remaining = resp.headers.get("X-RateLimit-Remaining") or resp.headers.get("X-Ratelimit-Remaining")
        if limit is None or remaining is None:
            return {
                "service": "Pixabay",
                "status": "call succeeded (key is valid) but no rate-limit headers found — "
                          "check response headers manually if you need exact numbers",
                "live": False,
            }
        return {
            "service": "Pixabay",
            "live": True,
            "used": int(limit) - int(remaining),
            "limit": int(limit),
            "note": "rolling 60s window, not a monthly balance",
        }
    except Exception as e:
        return {"service": "Pixabay", "status": f"error: {e}", "live": False}


def check_youtube_estimated_quota() -> dict:
    """
    YouTube's quota is unit-based, not call-based (an upload costs ~1600
    units, a playlist insert ~50, a simple list ~1), against a default
    10,000/day budget. A flat call count wouldn't mean much, so this sums
    self-tracked per-operation-type counts weighted by known costs.

    This is an ALL-TIME cumulative estimate, not a "today" figure — the
    log doesn't bucket by date. Treat it as directional; Cloud Console is
    the authoritative source for actual remaining daily quota.
    """
    dashboard_url = "https://console.cloud.google.com/apis/dashboard"

    if not USAGE_LOG_PATH.exists():
        return {
            "service": "YouTube Data API",
            "live": False,
            "status": f"no live endpoint available — self-tracking not yet wired in. Check manually: {dashboard_url}",
        }

    # (log key, display name, cost in quota units)
    operations = [
        ("youtube_upload", "uploads", 1600),
        ("youtube_playlist_create", "playlist creations", 50),
        ("youtube_playlist_item_insert", "playlist item adds", 50),
        ("youtube_playlist_list", "playlist list calls", 1),
        ("youtube_playlist_item_list", "playlist item checks", 1),
    ]

    try:
        log = json.loads(USAGE_LOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"service": "YouTube Data API", "live": False, "status": f"could not read local usage log. Check manually: {dashboard_url}"}

    breakdown = []
    total_units = 0
    total_calls = 0
    for key, label, cost in operations:
        count = log.get(key, {}).get("count", 0)
        if count:
            units = count * cost
            total_units += units
            total_calls += count
            breakdown.append(f"{count} {label} (~{units:,} units)")

    if total_calls == 0:
        return {"service": "YouTube Data API", "live": False, "status": f"no calls logged yet. Check manually: {dashboard_url}"}

    return {
        "service": "YouTube Data API",
        "live": False,
        "status": (
            f"self-tracked, ALL-TIME estimate: ~{total_units:,} quota units "
            f"({'; '.join(breakdown)}). Default daily budget is 10,000 units — "
            f"this is cumulative, not today's usage. Authoritative source: {dashboard_url}"
        ),
    }


def check_self_tracked(service_key: str, display_name: str, dashboard_url: str) -> dict:
    """Reads locally self-tracked call counts, if usage_tracker.py has been wired in."""
    if not USAGE_LOG_PATH.exists():
        return {
            "service": display_name,
            "live": False,
            "status": f"no live endpoint available — self-tracking not yet wired in. "
                      f"Check manually: {dashboard_url}",
        }
    try:
        log = json.loads(USAGE_LOG_PATH.read_text(encoding="utf-8"))
        count = log.get(service_key, {}).get("count", 0)
        since = log.get(service_key, {}).get("since", "unknown")
        return {
            "service": display_name,
            "live": False,
            "status": f"self-tracked: {count} calls logged locally since {since}. "
                      f"For real quota: {dashboard_url}",
        }
    except Exception:
        return {
            "service": display_name,
            "live": False,
            "status": f"could not read local usage log. Check manually: {dashboard_url}",
        }


def print_console_report(results: list):
    print("\n" + "=" * 60)
    print("API USAGE DASHBOARD")
    print("=" * 60)
    for r in results:
        print(f"\n{r['service']}:")
        if r.get("live"):
            print(f"  Used:    {r['used']:,} / {r['limit']:,} ({r.get('pct', '?')}%)")
            if r.get("resets"):
                print(f"  Resets:  {r['resets']}")
            if r.get("note"):
                print(f"  Note:    {r['note']}")
        else:
            print(f"  {r.get('status', 'unknown')}")
    print("\n" + "=" * 60)


def write_html_dashboard(results: list, output_path: str = "usage_dashboard.html"):
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows = ""
    for r in results:
        if r.get("live"):
            pct = r.get("pct", 0)
            bar_color = "#2ecc71" if pct < 70 else ("#f39c12" if pct < 90 else "#e74c3c")
            rows += f"""
            <div class="card">
              <h3>{r['service']}</h3>
              <div class="bar-bg"><div class="bar-fill" style="width:{min(pct,100)}%;background:{bar_color};"></div></div>
              <p>{r['used']:,} / {r['limit']:,} used ({pct}%)</p>
              {"<p class='meta'>Resets: " + r['resets'] + "</p>" if r.get('resets') else ""}
              {"<p class='meta'>" + r['note'] + "</p>" if r.get('note') else ""}
            </div>"""
        else:
            rows += f"""
            <div class="card unavailable">
              <h3>{r['service']}</h3>
              <p class="meta">{r.get('status', 'unavailable')}</p>
            </div>"""

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>API Usage Dashboard</title>
<style>
  body {{ font-family: -apple-system, sans-serif; background: #0f1115; color: #e8e8e8; padding: 40px; }}
  h1 {{ font-size: 1.4em; }}
  .timestamp {{ color: #888; margin-bottom: 30px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
  .card {{ background: #1a1d24; border-radius: 10px; padding: 18px; }}
  .card.unavailable {{ opacity: 0.6; }}
  .card h3 {{ margin: 0 0 10px 0; }}
  .bar-bg {{ background: #2a2d35; border-radius: 6px; height: 10px; overflow: hidden; }}
  .bar-fill {{ height: 100%; }}
  .meta {{ color: #999; font-size: 0.85em; }}
</style>
</head>
<body>
  <h1>You Never Knew — API Usage Dashboard</h1>
  <p class="timestamp">Generated {generated_at} — re-run check_usage.py to refresh</p>
  <div class="grid">
    {rows}
  </div>
</body>
</html>"""

    Path(output_path).write_text(html, encoding="utf-8")
    print(f"\nDashboard written to {Path(output_path).resolve()} — open it in a browser.")


def main():
    results = [
        check_elevenlabs(),
        check_pexels(),
        check_pixabay(),
        check_self_tracked("jamendo", "Jamendo", "https://devportal.jamendo.com/"),
        check_self_tracked("gemini", "Gemini", "https://aistudio.google.com/usage"),
        check_youtube_estimated_quota(),
    ]
    print_console_report(results)
    write_html_dashboard(results)


if __name__ == "__main__":
    main()
