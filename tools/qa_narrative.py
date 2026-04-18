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


QA_PROMPT = """You are a strict fact-checker for a fixed income market report.

You will receive:
1. A narrative with an intro paragraph and bullet points written by an analyst
2. The validated data payload the narrative should be grounded in

Check the following and return a JSON object:

CHECKS:
A. Every numeric figure in the narrative (yields in %, spreads in bps, returns in %)
   must match the corresponding JSON value within ±1bp/1bps/0.01% tolerance.
B. Directional language ("rose", "fell", "tightened", "widened", "steepened", "flattened")
   must be consistent with the sign of the MTD change fields in the payload.
C. No Fed official should be attributed a quote or stance not present in fed_speakers.
   If fed_speakers is empty, no speaker-specific claims should appear in the narrative.
D. If late_breaking_events contains any event dated Wednesday or later,
   that event must appear in the narrative.
E. No figure should be cited as the Friday close if its observation_date != week_ending,
   unless it is flagged inline with [DATA: as of {date}].

RETURN FORMAT — respond only with valid JSON, no prose:
{
  "status": "PASS",
  "failures": []
}
OR
{
  "status": "FAIL",
  "failures": [
    "A: Narrative cites 10yr at 4.35% but payload shows 4.32%",
    "D: Iran Strait of Hormuz event (2026-04-17) not mentioned in narrative"
  ]
}"""


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
        {"status": "PASS", "failures": []}
        {"status": "FAIL", "failures": ["A: ...", "D: ..."]}
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
        max_tokens=1024,
        system=QA_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = msg.content[0].text.strip()

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

    return json.loads(raw)


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
