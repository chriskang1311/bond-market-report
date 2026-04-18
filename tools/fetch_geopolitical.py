"""
tools/fetch_geopolitical.py

Uses Tavily to find late-breaking geopolitical or macro events from the past 7 days
that affected bond markets or the rate outlook.

Standalone test:
    python3 tools/fetch_geopolitical.py
"""

import os
import json
from datetime import date, timedelta
from dotenv import load_dotenv
import anthropic

SEARCH_QUERIES = [
    "geopolitical events bond market treasury yields impact this week",
    "oil prices trade tariffs inflation shock economic data this week bonds",
]

WEEK_AGO = (date.today() - timedelta(days=7)).isoformat()


def _search_tavily(query: str, api_key: str) -> list[dict]:
    import requests
    resp = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key":                api_key,
            "query":                  query,
            "search_depth":           "basic",
            "max_results":            5,
            "include_published_date": True,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("results", [])


def _parse_events_with_claude(raw_results: list[dict], anthropic_api_key: str) -> list[dict]:
    if not raw_results:
        return []

    snippets = "\n\n".join(
        f"[{r.get('published_date', 'unknown date')}] {r.get('title', '')}\n{r.get('content', '')[:400]}\nURL: {r.get('url', '')}"
        for r in raw_results
    )

    prompt = f"""Extract significant geopolitical or macro events from these search results that affected or could affect bond markets or the Fed rate outlook. Today is {date.today()}.

SEARCH RESULTS:
{snippets}

Return a JSON array. Each element must have exactly these fields:
- "event": concise event description (1 sentence, e.g. "Iran reopens Strait of Hormuz")
- "date": ISO date the event occurred (e.g. "2026-04-17")
- "market_impact": how it affected bond yields, spreads, or rate expectations (1 sentence)
- "source_url": the URL

Only include events from the past 7 days (since {WEEK_AGO}).
Only include events with clear relevance to fixed income markets.
If no relevant events found, return an empty array [].
Return only valid JSON, no prose."""

    client = anthropic.Anthropic(api_key=anthropic_api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def fetch_geopolitical(tavily_api_key: str, anthropic_api_key: str) -> list[dict]:
    """
    Search for late-breaking geopolitical and macro events affecting bond markets.

    Returns:
        [
            {
                "event": "Iran reopens Strait of Hormuz",
                "date": "2026-04-17",
                "market_impact": "Sharp oil drop boosted Dec cut probability and briefly rallied Treasuries",
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

    return _parse_events_with_claude(all_results, anthropic_api_key)


if __name__ == "__main__":
    load_dotenv()
    events = fetch_geopolitical(
        tavily_api_key=os.environ["TAVILY_API_KEY"],
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
    )
    print(json.dumps(events, indent=2))
