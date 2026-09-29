"""
Gemini integration for the You Never Knew video factory.

Responsibilities (kept isolated from main.py so the AI provider can be
swapped later without touching the rest of the pipeline):

  - loading the Gemini API key from the environment
  - configuring the Gemini client
  - generating a candidate topic (Layer 1 protection: prompt-level exclusion)
  - generating a structured script for an approved topic
  - independently validating Gemini's JSON output before it is trusted

Python (topic_engine.py) remains the final authority on topic uniqueness
(Layer 2 protection). This module never writes to database/topics.json or
database/videos.json directly.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import List, Optional

try:
    # Optional: picks up a local .env file for local testing. In GitHub
    # Actions the secret is injected directly as an environment variable,
    # so this is a no-op there (no .env file present).
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from google import genai
from google.genai import types

from . import topic_engine
from . import usage_tracker


MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

# Tried in order, once each per round, when the primary model is failing
# (e.g. the recurring 503 "high demand" spikes). Comma-separated env var
# overrides the default. A model name that doesn't exist just fails fast and
# the loop moves on, so a stale name here is harmless but useless — keep it
# current. Set GEMINI_FALLBACK_MODELS="" to disable fallbacks entirely.
FALLBACK_MODELS = [
    m.strip()
    for m in os.environ.get("GEMINI_FALLBACK_MODELS", "gemini-3.8-flash").split(",")
    if m.strip() and m.strip() != MODEL_NAME
]
# Waits between rounds when failures look transient (503 / 429 / 5xx). The
# repo is public so Actions minutes are free; patience costs nothing, and the
# rolling publish buffer means a late-finishing run still lands on schedule.
# Sum = ~32 min. Override the whole schedule with GEMINI_WAIT_SCHEDULE="60,120,...".
TRANSIENT_WAIT_SCHEDULE = [
    int(x) for x in os.environ.get(
        "GEMINI_WAIT_SCHEDULE", "60,120,240,300,300,300,300,300"
    ).split(",") if x.strip()
]
NON_TRANSIENT_WAIT_SECONDS = 15
TRANSIENT_MARKERS = (
    "503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED",
    "500", "INTERNAL", "504", "DEADLINE", "overloaded", "high demand",
)


def _is_transient(err: Exception) -> bool:
    msg = str(err)
    return any(marker in msg for marker in TRANSIENT_MARKERS)

_client: Optional["genai.Client"] = None


class GeminiError(Exception):
    """Raised for anything that goes wrong talking to Gemini."""


class ScriptValidationError(Exception):
    """Raised when Gemini's script JSON fails validation."""


# ---------------------------------------------------------------------------
# Client setup
# ---------------------------------------------------------------------------

def _get_client():
    global _client
    if _client is not None:
        return _client

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise GeminiError(
            "GEMINI_API_KEY is not set. Set it as an environment variable "
            "(a local .env file for local testing, or a GitHub Actions "
            "secret named GEMINI_API_KEY for automation). Never hard-code "
            "it in config.json or source files."
        )
    _client = genai.Client(api_key=api_key)
    return _client


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _call_gemini(
    prompt: str,
    system_instruction: Optional[str] = None,
    json_mode: bool = False,
    max_retries: int = 3,
) -> str:
    """Low-level Gemini call with retry on transient failures."""
    client = _get_client()

    config_kwargs = {}
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction
    if json_mode:
        config_kwargs["response_mime_type"] = "application/json"

    config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

    models = [MODEL_NAME] + FALLBACK_MODELS
    last_error = None
    errors_by_model: dict[str, Exception] = {}  # latest error per model
    dead_models: set[str] = set()  # 404 / not-found: don't retry these
    transient_rounds = 0
    other_rounds = 0
    total_rounds = 0

    while True:
        total_rounds += 1
        round_had_transient = False
        # One pass over the primary model, then each fallback.
        for model in models:
            if model in dead_models:
                continue
            try:
                usage_tracker.log_call("gemini")
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                text = (response.text or "").strip()
                if not text:
                    raise GeminiError("Gemini returned an empty response.")
                if model != MODEL_NAME:
                    print(f"  Gemini: succeeded on fallback model {model}.")
                return text
            except Exception as e:  # noqa: BLE001
                last_error = e
                errors_by_model[model] = e
                msg = str(e)
                if "404" in msg or "NOT_FOUND" in msg:
                    dead_models.add(model)
                    print(f"  Gemini model {model} is unavailable (404); "
                          f"removing it from rotation: {e}")
                    continue
                if _is_transient(e):
                    round_had_transient = True
                print(f"  Gemini call failed on {model}: {e}")

        if all(m in dead_models for m in models):
            break  # nothing left to retry; waiting won't help

        if round_had_transient:
            transient_rounds += 1
            if transient_rounds > len(TRANSIENT_WAIT_SCHEDULE):
                break
            wait = TRANSIENT_WAIT_SCHEDULE[transient_rounds - 1]
            print(f"  Transient failure on all models (round {transient_rounds}/"
                  f"{len(TRANSIENT_WAIT_SCHEDULE) + 1}). Waiting {wait}s...")
        else:
            other_rounds += 1
            if other_rounds >= max_retries:
                break
            wait = NON_TRANSIENT_WAIT_SECONDS
            print(f"  Non-transient failure (round {other_rounds}/{max_retries}). "
                  f"Waiting {wait}s...")
        time.sleep(wait)

    # Report every model's error, not just the last one.
    detail = " | ".join(f"{m}: {err}" for m, err in errors_by_model.items())
    raise GeminiError(
        f"Gemini call failed after {total_rounds} rounds. "
        f"{detail or last_error}"
    )


# ---------------------------------------------------------------------------
# Topic generation (Layer 1 protection lives here; Layer 2 is topic_engine)
# ---------------------------------------------------------------------------

TOPIC_SYSTEM_INSTRUCTION = """You are generating video topics for the YouTube channel "You Never Knew".

Each video is titled "5 Facts You Didn't Know About [Topic]" and covers a mix
of animals, nature, science, geography, everyday objects, history, technology,
phenomena, and unusual places. Maintain variety across those categories rather
than defaulting to animals every time.

A good topic:
- has at least five genuinely interesting, distinct, well-established facts
- can be reasonably illustrated with stock footage/photos (avoid overly
  abstract, obscure, or unillustratable subjects)
- is specific enough to be a real subject, not a vague theme

Do not propose a topic that is an exact duplicate, a trivial rewording, or an
obvious narrow variation of an already-used topic. Genuinely distinct related
topics ARE allowed (for example "Volcanoes" and "Volcano Lightning" are
different videos, as are "Saturn" and "Saturn's Rings").

Return ONLY the topic name itself. No numbering, no quotation marks, no
markdown, no explanation, no extra commentary."""


def _build_topic_prompt(exclude_topics: List[str], performance_context: str = "") -> str:
    exclusion_text = "\n".join(f"- {t}" for t in exclude_topics) if exclude_topics else "(none yet)"
    context_block = f"\n{performance_context}\n" if performance_context else ""
    return (
        "Previously used or reserved topics on this channel (do NOT repeat "
        "these, and avoid trivial rewordings or narrow variations of them):\n\n"
        f"{exclusion_text}\n"
        f"{context_block}\n"
        "Propose one new topic for a \"5 Facts You Didn't Know About [Topic]\" "
        "video. Respond with ONLY the topic name, e.g.: Bioluminescent Jellyfish"
    )


def generate_candidate_topic(exclude_topics: List[str], performance_context: str = "") -> str:
    """Ask Gemini for a single candidate topic. Does NOT check uniqueness itself."""
    raw = _call_gemini(
        _build_topic_prompt(exclude_topics, performance_context),
        system_instruction=TOPIC_SYSTEM_INSTRUCTION,
        json_mode=False,
    )
    # Defensive cleanup in case the model adds quotes/markdown/numbering anyway.
    candidate = raw.strip().splitlines()[0].strip()
    candidate = candidate.strip("\"'“”")
    candidate = re.sub(r"^\d+[\.\)]\s*", "", candidate)
    candidate = candidate.strip(" -*")
    return candidate.strip()


def get_unique_topic(max_attempts: int = 5, performance_context: str = "") -> str:
    """
    Two-layer topic protection:
      Layer 1 (prompt-level): Gemini is shown the exclusion list and told
        not to propose those topics or trivial variations of them.
      Layer 2 (Python-level): every candidate is independently verified
        with topic_engine.is_duplicate(), which is the final authority.

    performance_context, when given (see engines/analytics.py
    build_performance_context()), is appended to the prompt as a soft
    nudge toward categories that have retained viewers well recently —
    it never overrides the exclusion/variety rules above.

    Retries with a growing exclusion list if Gemini proposes a duplicate.
    Does NOT reserve the topic — call topic_engine.reserve_topic() after
    this returns.
    """
    exclude = topic_engine.get_all_used_topics()

    for attempt in range(1, max_attempts + 1):
        candidate = generate_candidate_topic(exclude, performance_context)
        if not candidate:
            continue
        if topic_engine.is_duplicate(candidate):
            print(f"  Gemini proposed a duplicate topic ('{candidate}'), retrying ({attempt}/{max_attempts})...")
            exclude = exclude + [candidate]
            continue
        return candidate

    raise GeminiError(f"Could not obtain a unique topic after {max_attempts} attempts.")


# ---------------------------------------------------------------------------
# Script generation
# ---------------------------------------------------------------------------

SCRIPT_SYSTEM_INSTRUCTION = """You write scripts for the YouTube channel "You Never Knew" in the
"5 Facts You Didn't Know About [Topic]" format.

Style requirements:
- Fascinating, surprising, concise, engaging, and natural for voice narration.
- Exactly 5 facts. Each fact must be a genuinely distinct piece of
  information, not the same idea reworded.
- Strong, exciting hook.
- Ending highlights how fascinating the topic is, encourages viewers to
  subscribe to "You Never Knew", and asks a specific question in the comments.

Factual accuracy requirements (Version 1 has no external fact-checking, so
you must be conservative):
- Facts must be accurate and use well-established information.
- Do not invent facts, statistics, measurements, scientific explanations,
  historical claims, or anecdotes.
- Do not exaggerate uncertain claims as established fact.
- If you are uncertain about a claim, use a different fact instead.
- Avoid disputed or poorly established claims unless clearly identified as such.
- Do not sacrifice accuracy for sensationalism.

Visual prompt requirements:
- Each fact has one "visual_prompt" describing ONLY what should be shown
  visually (vivid, concrete, suitable for stock footage search).
- Do NOT include captions, text overlays, or any on-screen text in the
  visual prompt or anywhere else in the response.

Return ONLY strict JSON matching this shape, with no markdown fences and no
commentary outside the JSON:

{
  "topic": "string",
  "hook": "string",
  "facts": [
    {"number": 1, "narration": "string", "visual_prompt": "string"},
    {"number": 2, "narration": "string", "visual_prompt": "string"},
    {"number": 3, "narration": "string", "visual_prompt": "string"},
    {"number": 4, "narration": "string", "visual_prompt": "string"},
    {"number": 5, "narration": "string", "visual_prompt": "string"}
  ],
  "ending": "string"
}"""


def _build_script_prompt(topic: str) -> str:
    return f"""Create a "You Never Knew" five-fact script.

Topic: {topic}

Follow the JSON shape and all requirements given in the system instructions
exactly. Do not include a "caption" field anywhere."""


def validate_generated_script(data: dict) -> dict:
    """
    Independently validate Gemini's script JSON before it is trusted.
    Never consume ElevenLabs credits on an unvalidated script.
    Returns a cleaned dict matching the structure parse_script() produces
    (fact_number left as None; main.py fills it in after reservation).
    """
    if not isinstance(data, dict):
        raise ScriptValidationError("Gemini script response is not a JSON object.")

    topic = data.get("topic")
    if not topic or not isinstance(topic, str) or not topic.strip():
        raise ScriptValidationError("Missing or empty 'topic'.")

    hook = data.get("hook")
    if not hook or not isinstance(hook, str) or not hook.strip():
        raise ScriptValidationError("Missing or empty 'hook'.")

    ending = data.get("ending")
    if not ending or not isinstance(ending, str) or not ending.strip():
        raise ScriptValidationError("Missing or empty 'ending'.")

    facts = data.get("facts")
    if not isinstance(facts, list) or len(facts) != 5:
        got = len(facts) if isinstance(facts, list) else "none"
        raise ScriptValidationError(f"Expected exactly 5 facts, got {got}.")

    seen_numbers = []
    cleaned_facts = []
    for i, fact in enumerate(facts, start=1):
        if not isinstance(fact, dict):
            raise ScriptValidationError(f"Fact {i} is not an object.")

        if "caption" in fact or "captions" in fact:
            raise ScriptValidationError(f"Fact {i} contains a forbidden 'caption' field.")

        number = fact.get("number", i)
        try:
            number = int(number)
        except (TypeError, ValueError):
            raise ScriptValidationError(f"Fact {i} has a non-integer 'number'.")
        if number in seen_numbers:
            raise ScriptValidationError(f"Duplicate fact number: {number}.")
        seen_numbers.append(number)

        narration = fact.get("narration")
        if not narration or not isinstance(narration, str) or not narration.strip():
            raise ScriptValidationError(f"Fact {i} is missing narration.")

        visual_prompt = fact.get("visual_prompt")
        if not visual_prompt or not isinstance(visual_prompt, str) or not visual_prompt.strip():
            raise ScriptValidationError(f"Fact {i} is missing visual_prompt.")

        cleaned_facts.append({
            "number": number,
            "narration": narration.strip(),
            "visual_prompt": visual_prompt.strip(),
        })

    if sorted(seen_numbers) != [1, 2, 3, 4, 5]:
        raise ScriptValidationError(f"Fact numbers must be exactly 1-5, got {sorted(seen_numbers)}.")

    cleaned_facts.sort(key=lambda f: f["number"])

    return {
        "fact_number": None,  # numbering.py fills this in after topic reservation
        "topic": topic.strip(),
        "hook": hook.strip(),
        "facts": cleaned_facts,
        "ending": ending.strip(),
    }


def generate_script(topic: str, max_retries: int = 3) -> dict:
    """
    Generate and validate a script for an ALREADY-APPROVED, already-unique
    topic. Does not touch topic_engine or numbering — call this only after
    reserve_topic() has succeeded.
    """
    prompt = _build_script_prompt(topic)

    last_error = None
    for attempt in range(1, max_retries + 1):
        raw = _call_gemini(prompt, system_instruction=SCRIPT_SYSTEM_INSTRUCTION, json_mode=True)
        try:
            data = json.loads(_strip_json_fences(raw))
        except json.JSONDecodeError as e:
            last_error = f"Invalid JSON: {e}"
            print(f"  Script generation attempt {attempt} failed ({last_error}), retrying...")
            continue

        try:
            return validate_generated_script(data)
        except ScriptValidationError as e:
            last_error = str(e)
            print(f"  Script generation attempt {attempt} failed validation ({last_error}), retrying...")
            continue

    raise GeminiError(f"Could not generate a valid script after {max_retries} attempts: {last_error}")
