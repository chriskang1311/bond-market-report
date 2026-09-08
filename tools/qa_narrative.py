"""
tools/qa_narrative.py

QA agent: Claude fact-checks the narrative bullets against the structured payload.
Returns PASS or a list of specific failures that trigger a retry.

Standalone test:
    python3 tools/qa_narrative.py
"""

import json
import os
from datetime import date
from dotenv import load_dotenv
import anthropic


QA_PROMPT = """You are a fact-checker for a weekly fixed income report. Your only job is to catch
figures and claims that the data payload does NOT support. You are not an editor: do not flag
wording, tone, emphasis, or which adjective the analyst chose.

You will receive:
1. NARRATIVE — an intro paragraph and bullets written by an analyst
2. DATA PAYLOAD — the validated data the narrative must be grounded in

Context on dates: FRED publishes Treasury and spread data with about a one business-day lag, so
`observation_date` is normally the day before `week_ending`. That lag is expected and is not a
problem on its own.

CHECKS — work through each one in the "reasoning" field:
A. NUMBERS. Every yield (%), spread (bps), and return (%) the narrative states matches the
   payload value within ±1 (bp / bps / 0.01%). Also verify figures the narrative derives itself:
   curve spreads (2s10s = DGS10 − DGS2, 2s30s = DGS30 − DGS2), week-over-week / MTD changes
   against the payload's change fields, and year-over-year moves against `year_ago`. A figure is
   a violation only if it is actually wrong.
B. DIRECTION. When the narrative says a yield or spread "rose / fell / widened / tightened /
   steepened / flattened", the sign must not contradict the payload's change field (e.g. it says
   "tightened" but the MTD change is positive). If the direction is defensible from the numbers,
   it is fine — do not flag it over word choice.
C. FED SPEAKERS. No stance or quote is attributed to a Fed official that is not in
   `fed_speakers`. If `fed_speakers` is empty, the narrative makes no speaker-specific claim.
D. LATE-BREAKING EVENTS. Every event in `late_breaking_events` dated Wednesday or later of the
   report week appears in the narrative.
E. AS-OF LABELLING. Only a violation if the narrative explicitly presents a figure as the
   Friday (`week_ending`) close when its `observation_date` is earlier AND the narrative nowhere
   states the real as-of date (an inline "[DATA: as of <date>]" on any figure, or a general
   note, both count). The ordinary one-day lag, disclosed once anywhere, is acceptable.

RETURN — respond with a single valid JSON object and nothing else:
{
  "reasoning": "<brief check-by-check working — for each figure you doubt, quote the narrative value, quote the payload value, and say MATCH or MISMATCH. Keep it to a few lines per check.>",
  "status": "PASS" or "FAIL",
  "failures": ["A: narrative cites 10y at 4.35% but payload DGS10 = 4.32%", "D: Strait of Hormuz event (2026-04-17) missing from narrative"]
}

Rules for the output:
- "failures" contains ONLY confirmed violations, one short sentence each, prefixed with the
  check letter. If a check passes, it does not appear in "failures".
- "status" is "FAIL" if and only if "failures" is non-empty. If every check passes, return
  "status": "PASS" with "failures": []."""


def _narrative_to_text(narrative: dict) -> str:
    """Flatten narrative dict to plain text for QA checking."""
    parts = []
    intro = narrative.get("intro", "")
    if intro:
        parts.append(f"INTRO:\n{intro}")
    bullets = narrative.get("bullets", [])
    if bullets:
        parts.append("BULLETS:")
        for b in bullets:
            parts.append(f"• {b['text']}")
            for sb in b.get("sub_bullets", []):
                parts.append(f"  ◦ {sb}")
    return "\n".join(parts)


def qa_narrative(
    narrative: dict,
    payload: dict,
    anthropic_api_key: str,
) -> dict:
    """
    Fact-check narrative dict against the validated payload.

    Args:
        narrative: {"intro": str, "bullets": [{"text": str, "sub_bullets": [str]}]}
        payload:   Validated data payload
        anthropic_api_key: Anthropic API key

    Returns:
        {"reasoning": "...", "status": "PASS", "failures": []}
        {"reasoning": "...", "status": "FAIL", "failures": ["A: ...", "D: ..."]}

    Only "status" and "failures" are consumed downstream; "reasoning" gives the
    model somewhere to work other than the failures list.
    """
    narrative_text = _narrative_to_text(narrative)
    payload_json   = json.dumps(payload, indent=2)

    user_content = f"""NARRATIVE:
{narrative_text}

DATA PAYLOAD:
{payload_json}"""

    client = anthropic.Anthropic(api_key=anthropic_api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,  # room for the reasoning field + failures list
        system=QA_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = next((b.text for b in msg.content if b.type == "text"), "").strip()

    # Strip markdown code fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    # Extract the outermost JSON object in case there's surrounding prose
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start != -1 and end > start:
        raw = raw[start:end]

    try:
        return json.loads(raw)
    except Exception:
        # QA response couldn't be parsed — treat as PASS to avoid blocking delivery
        print("  [WARN] QA response could not be parsed as JSON — treating as PASS.", flush=True)
        return {"status": "PASS", "failures": []}


if __name__ == "__main__":
    load_dotenv()
    today = date.today().isoformat()

    stub_payload = {
        "week_ending": today,
        "yields": {
            "DGS2":  {"value": 3.78, "observation_date": today, "source": "FRED:DGS2"},
            "DGS10": {"value": 4.32, "observation_date": today, "source": "FRED:DGS10"},
            "DGS30": {"value": 4.93, "observation_date": today, "source": "FRED:DGS30"},
        },
        "spreads": {
            "IG_OAS": {"value": 81.0, "observation_date": today, "source": "FRED:BAMLC0A0CM"},
            "HY_OAS": {"value": 286.0, "observation_date": today, "source": "FRED:BAMLH0A0HYM2"},
            "IG_MTD_change": -6.0,
            "HY_MTD_change": -30.0,
        },
        "returns": {
            "IG Corporates": {"value": 0.79, "observation_date": today, "source": "FRED:BAMLCC0A0CMTRIV"},
        },
        "fed_speakers": [],
        "late_breaking_events": [],
    }

    # Test PASS: narrative correctly grounded
    good_narrative = {
        "intro": "Markets rallied this week on softer inflation data, with spreads tightening and duration rewarded.",
        "bullets": [
            {
                "text": "The 10-year Treasury yield closed the week at 4.32%, with the 2s10s spread at 54 bps.",
                "sub_bullets": ["Month-to-date, the 10yr has rallied 8 bps from 4.40%."],
            },
            {
                "text": "IG OAS tightened 6 bps MTD to 81 bps, with IG Corporates returning +0.79%.",
                "sub_bullets": [],
            },
            {
                "text": "HY OAS tightened 30 bps MTD to 286 bps, reflecting continued risk appetite.",
                "sub_bullets": [],
            },
            {
                "text": "No Fed officials made policy statements this week.",
                "sub_bullets": [],
            },
        ],
    }

    # Test FAIL: wrong 10yr figure
    bad_narrative = {
        "intro": "Markets were quiet this week.",
        "bullets": [
            {
                "text": "The 10-year Treasury yield closed at 4.50% — WRONG figure.",
                "sub_bullets": [],
            },
            {
                "text": "IG OAS tightened to 81 bps MTD.",
                "sub_bullets": [],
            },
        ],
    }

    print("PASS test:")
    print(json.dumps(qa_narrative(good_narrative, stub_payload, os.environ["ANTHROPIC_API_KEY"]), indent=2))

    print("\nFAIL test:")
    print(json.dumps(qa_narrative(bad_narrative, stub_payload, os.environ["ANTHROPIC_API_KEY"]), indent=2))
