import re


class ScriptParseError(Exception):
    pass


def parse_script(raw_text: str, fact_number: int = None) -> dict:
    """
    Parse a raw script into structured JSON. Tolerant of:
    - optional leading '#' / '##' markdown headers
    - straight or curly quotes
    - straight or curly apostrophes
    """
    text = raw_text.replace("\r\n", "\n")

    # Topic from the title line (with or without leading #)
    title_match = re.search(
        r"^#{0,2}\s*Script:\s*5 Facts You Didn.?t Know About\s*(.+)$",
        text, re.MULTILINE,
    )
    if not title_match:
        raise ScriptParseError("Could not find a 'Script: 5 Facts You Didn't Know About ...' title line.")
    topic = title_match.group(1).strip()

    quote = r"[\"\u201c]"      # opening straight or curly DOUBLE quote only
    end_quote = r"[\"\u201d]"  # closing straight or curly DOUBLE quote only

    # Hook
    hook_match = re.search(
        rf"^#{{0,2}}\s*Hook:\s*\n+\s*{quote}(.+?){end_quote}",
        text, re.DOTALL | re.MULTILINE,
    )
    if not hook_match:
        raise ScriptParseError("Could not find a 'Hook:' section.")
    hook = hook_match.group(1).strip()

    # Facts 1-5
    fact_pattern = re.compile(
        rf"^#{{0,2}}\s*Fact\s*(\d+):\s*\n+"
        rf"Narration:\s*\n+\s*{quote}(.+?){end_quote}\s*\n+"
        rf"InVideo Prompt:\s*\n+\s*{quote}(.+?){end_quote}",
        re.DOTALL | re.MULTILINE,
    )
    facts = []
    for m in fact_pattern.finditer(text):
        facts.append({
            "number": int(m.group(1)),
            "narration": m.group(2).strip(),
            "visual_prompt": m.group(3).strip(),
        })

    if len(facts) != 5:
        raise ScriptParseError(f"Expected 5 facts, found {len(facts)}. Check script formatting.")

    # Ending
    ending_match = re.search(
        rf"^#{{0,2}}\s*Ending:\s*\n+\s*{quote}(.+?){end_quote}",
        text, re.DOTALL | re.MULTILINE,
    )
    if not ending_match:
        raise ScriptParseError("Could not find an 'Ending:' section.")
    ending = ending_match.group(1).strip()

    return {
        "fact_number": fact_number,
        "topic": topic,
        "hook": hook,
        "facts": facts,
        "ending": ending,
    }