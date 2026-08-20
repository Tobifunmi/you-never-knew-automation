"""
Standalone Gemini integration tests for the You Never Knew pipeline.

Run these ONE AT A TIME, in order, confirming each works before moving on.
This deliberately does not touch main.py, topics.json, or videos.json in a
way that matters for the "auth" and "call" tests. "topic" and "script" tests
call real Gemini + do real (Layer 2) duplicate checks, but do NOT reserve
anything, so they're safe to run repeatedly.

Usage:
    python test_gemini.py auth
    python test_gemini.py call
    python test_gemini.py topic
    python test_gemini.py duplicate
    python test_gemini.py script
"""
from __future__ import annotations

import argparse
import json
import sys

from engines import gemini
from engines import topic_engine


def test_auth():
    print("Checking for GEMINI_API_KEY and initializing the client...")
    gemini._get_client()
    print("OK: client initialized.")


def test_call():
    print("Making a minimal Gemini call...")
    text = gemini._call_gemini("Reply with exactly the word: OK")
    print(f"Response: {text!r}")


def test_topic():
    print("Requesting a candidate topic from Gemini (Layer 1 + Layer 2 checked)...")
    topic = gemini.get_unique_topic()
    print(f"Candidate unique topic: {topic}")
    print("(Not reserved — this was just a test.)")


def test_duplicate():
    print("Verifying Python correctly rejects a known-used topic...")
    used = topic_engine.get_all_used_topics()
    if not used:
        print("SKIPPED: topics.json has no completed/reserved topics to test against.")
        return
    existing = used[0]
    if topic_engine.is_duplicate(existing):
        print(f"OK: '{existing}' correctly detected as a duplicate.")
    else:
        print(f"FAIL: '{existing}' was NOT detected as a duplicate.")
        sys.exit(1)


def test_script():
    topic = "Test Topic For Gemini Script Generation"
    print(f"Requesting a script for topic: {topic}")
    script = gemini.generate_script(topic)
    print(json.dumps(script, indent=2))
    print("OK: script generated and passed validation (fact_number is None here on purpose).")


TESTS = {
    "auth": test_auth,
    "call": test_call,
    "topic": test_topic,
    "duplicate": test_duplicate,
    "script": test_script,
}


def main():
    parser = argparse.ArgumentParser(description="Gemini integration tests.")
    parser.add_argument("test", choices=list(TESTS.keys()))
    args = parser.parse_args()
    TESTS[args.test]()


if __name__ == "__main__":
    main()
