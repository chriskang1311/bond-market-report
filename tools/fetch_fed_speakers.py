"""
tools/fetch_fed_speakers.py

Uses Tavily to find Fed official statements from the past 7 days.
Returns a structured list — one object per official.

Standalone test:
    python3 tools/fetch_fed_speakers.py
"""

import os
import json
from datetime import date, timedelta
from dotenv import load_dotenv
import anthropic

SEARCH_QUERIES = [
    "Federal Reserve officials speeches statements this week rates bonds",
    "Fed Chair Powell FOMC monetary policy statement this week",
]

WEEK_AGO = (date.today() - timedelta(days=7)).isoformat()


def _search_tavily(query: str, api_key: str) -> list[dict]:
    """Call Tavily search API, return list of result dicts."""
    import requests
    resp = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key":              api_key,
            "query":                query,
            "search_depth":         "basic",
            "max_results":          5,
            "include_published_date": True,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("results", [])


def _parse_speakers_with_claude(raw_results: list[dict], anthropic_api_key: str) -> list[dict]:
    """Use Claude to extract structured speaker objects from raw search results."""
    if not raw_results:
        return []

    snippets = "\n\n".join(
        f"[{r.get('published_date', 'unknown date')}] {r.get('title', '')}\n{r.get('content', '')[:400]}\nURL: {r.get('url', '')}"
        for r in raw_results
    )

    prompt = f"""Extract Federal Reserve official statements from these search results. Today is {date.today()}.

SEARCH RESULTS:
{snippets}

Return a JSON array. Each element must have exactly these fields:
- "official": full name (e.g. "Christopher Waller")
- "role": title (e.g. "Fed Governor", "NY Fed President")
- "date": ISO date of the statement (e.g. "2026-04-17")
- "stance": one of "hawkish", "dovish", "hold-hawkish", "hold-dovish", "neutral"
- "key_quote": the most specific quote or paraphrase (1 sentence)
- "source_url": the URL

Only include officials who made statements in the past 7 days (since {WEEK_AGO}).
Deduplicate by official name — keep only the most recent statement per person.
If no relevant statements found, return an empty array [].
Return only valid JSON, no prose."""

    client = anthropic.Anthropic(api_key=anthropic_api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def fetch_fed_speakers(tavily_api_key: str, anthropic_api_key: str) -> list[dict]:
    """
    Search for Fed official statements this week and return structured list.

    Returns:
        [
            {
                "official": "Beth Hammack",
                "role": "Cleveland Fed President",
                "date": "2026-04-15",
                "stance": "hold-hawkish",
                "key_quote": "My baseline is that we're going to remain on hold for a good while",
                "source_url": "https://..."
            },
            ...
        ]
        Empty list is valid — confirms sweep ran.
    """
    all_results = []
    for query in SEARCH_QUERIES:
        try:
            results = _search_tavily(query, tavily_api_key)
            all_results.extend(results)
        except Exception as e:
            print(f"  [WARN] Tavily search failed: {e}", flush=True)

    return _parse_speakers_with_claude(all_results, anthropic_api_key)


if __name__ == "__main__":
    load_dotenv()
    speakers = fetch_fed_speakers(
        tavily_api_key=os.environ["TAVILY_API_KEY"],
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
    )
    print(json.dumps(speakers, indent=2))
