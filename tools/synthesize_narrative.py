"""
tools/synthesize_narrative.py

Calls Claude to generate a rich weekly narrative from the validated payload:
  - An editorial intro paragraph ("Word on the Desk" style)
  - 5-7 detailed bullets, each 2-4 sentences, with 0-2 sub-bullets each

Standalone test:
    python3 tools/synthesize_narrative.py
"""

import json
import os
from datetime import date
from dotenv import load_dotenv
import anthropic

SYSTEM_PROMPT = """You are a senior fixed income portfolio manager writing a weekly market summary
for institutional clients — the style and depth of a firm like IR+M, BlackRock, or PIMCO.

You will receive a validated JSON data payload. Your output must be a single JSON object.

OUTPUT FORMAT (return only valid JSON, no prose outside it):
{
  "intro": "<3-5 sentence editorial paragraph — high-level take on the week's theme, portfolio implications, and what to watch>",
  "bullets": [
    {
      "text": "<main bullet: 2-4 sentences covering one specific topic with exact numbers>",
      "sub_bullets": ["<optional detail or nuance>", "<optional second sub-bullet>"]
    }
  ]
}

CONTENT RULES:
1. Every yield level, spread level, and return figure you cite must match the JSON value field exactly.
   Use the Friday close (week_ending date).

2. Cover ALL of these topics across the 5-7 bullets (one topic per bullet):
   - Macro / CPI / inflation data and its market impact
   - Treasury curve: absolute levels, week-over-week moves, curve shape (2s10s, 2s30s), direction
   - Investment-grade corporate credit: spreads in bps, MTD change, total returns, supply technicals
     (estimate weekly IG issuance volume from news context if available)
   - High-yield corporate credit: spreads in bps, MTD change, total returns, risk appetite signals
   - Agency MBS / securitized: performance vs. other sectors, prepayment/rate context if available
   - Geopolitical / macro events: any late_breaking_events must appear with market impact noted
   - Fed / monetary policy: each speaker stays distinct, never merged into a composite

3. Fed speaker positions must remain distinct. Each official gets their own sentence with their
   specific nuance. Never attribute a composite stance.

4. If late_breaking_events contains any event on or after Wednesday, it must appear in the bullets
   and its end-of-week pricing impact must be explicitly noted.

5. Sub-bullets should add a specific data point, secondary driver, or forward-looking implication
   that didn't fit in the main bullet. Keep sub-bullets to 1-2 sentences.

6. The intro paragraph should NOT repeat specific numbers from the bullets — it sets the narrative
   frame and portfolio positioning tone only.

7. Flag any figure where observation_date != week_ending with [DATA: as of {date}] inline.

8. Do not invent excess return data not present in the JSON. If MBS or muni data is absent,
   discuss what news context suggests about those sectors without citing made-up levels."""


def synthesize_narrative(
    payload: dict,
    anthropic_api_key: str,
    qa_failures: list[str] | None = None,
) -> dict:
    """
    Generate a rich narrative from the validated payload.

    Returns:
        {
            "intro": "3-5 sentence editorial paragraph...",
            "bullets": [
                {"text": "Main bullet 2-4 sentences...", "sub_bullets": ["detail..."]},
                ...
            ]
        }
    """
    payload_json = json.dumps(payload, indent=2)
    user_content = f"DATA PAYLOAD:\n{payload_json}"

    if qa_failures:
        failure_block = "\n".join(f"- {f}" for f in qa_failures)
        user_content = (
            f"Your previous draft had these specific issues that must be fixed:\n{failure_block}\n\n"
            + user_content
        )

    client = anthropic.Anthropic(api_key=anthropic_api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


if __name__ == "__main__":
    load_dotenv()
    today = date.today().isoformat()

    stub_payload = {
        "week_ending": today,
        "yields": {
            "week_ending": today,
            "DGS2":  {"value": 3.78, "observation_date": today, "source": "FRED:DGS2"},
            "DGS5":  {"value": 4.05, "observation_date": today, "source": "FRED:DGS5"},
            "DGS10": {"value": 4.32, "observation_date": today, "source": "FRED:DGS10"},
            "DGS20": {"value": 4.75, "observation_date": today, "source": "FRED:DGS20"},
            "DGS30": {"value": 4.93, "observation_date": today, "source": "FRED:DGS30"},
            "month_start": {"DGS2": 3.85, "DGS5": 4.12, "DGS10": 4.40, "DGS20": 4.80, "DGS30": 4.98},
            "year_ago":    {"DGS2": 4.90, "DGS5": 4.70, "DGS10": 4.55, "DGS20": 4.85, "DGS30": 4.95},
        },
        "spreads": {
            "IG_OAS":        {"value": 81.0, "observation_date": today, "source": "FRED:BAMLC0A0CM"},
            "HY_OAS":        {"value": 286.0, "observation_date": today, "source": "FRED:BAMLH0A0HYM2"},
            "IG_MTD_change": -6.0,
            "HY_MTD_change": -30.0,
        },
        "returns": {
            "IG Corporates": {"value": 0.79, "observation_date": today, "source": "FRED:BAMLCC0A0CMTRIV"},
            "HY Corporates": {"value": 1.33, "observation_date": today, "source": "FRED:BAMLHYH0A0HYM2TRIV"},
        },
        "fed_speakers": [
            {"official": "Beth Hammack", "role": "Cleveland Fed President",
             "date": today, "stance": "hold-hawkish",
             "key_quote": "My baseline is that we're going to remain on hold for a good while",
             "source_url": "https://example.com/hammack"},
            {"official": "Christopher Waller", "role": "Fed Governor",
             "date": today, "stance": "hold-conditional-dovish-optionality",
             "key_quote": "A reopened Strait of Hormuz could pave the way to cuts later this year",
             "source_url": "https://example.com/waller"},
        ],
        "late_breaking_events": [
            {"event": "Iran reopens Strait of Hormuz",
             "date": today,
             "market_impact": "Sharp oil price drop boosted December rate cut probability and briefly rallied Treasuries",
             "source_url": "https://example.com/hormuz"},
        ],
    }

    narrative = synthesize_narrative(stub_payload, os.environ["ANTHROPIC_API_KEY"])
    print("\n=== INTRO ===")
    print(narrative["intro"])
    print("\n=== BULLETS ===")
    for i, b in enumerate(narrative["bullets"], 1):
        print(f"\n{i}. {b['text']}")
        for sb in b.get("sub_bullets", []):
            print(f"   • {sb}")
