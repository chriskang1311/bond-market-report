"""
tools/fetch_spreads.py

Fetches IG and HY OAS credit spreads from FRED pinned to Friday close.
Converts from percent to basis points (× 100).

Standalone test:
    python3 tools/fetch_spreads.py
"""

import os
import certifi
import requests
from datetime import date, timedelta
from dotenv import load_dotenv

os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

SPREAD_SERIES = {
    "BAMLC0A0CM":  "IG_OAS",
    "BAMLH0A0HYM2": "HY_OAS",
}


def _most_recent_friday() -> date:
    today = date.today()
    return today - timedelta(days=(today.weekday() - 4) % 7)


def _month_start() -> date:
    today = date.today()
    return date(today.year, today.month, 1)


def _fetch_latest_on_or_before(series_id: str, as_of: date, api_key: str) -> dict:
    """Fetch most recent non-null value on or before as_of."""
    params = {
        "series_id":       series_id,
        "api_key":         api_key,
        "file_type":       "json",
        "observation_end": as_of.isoformat(),
        "sort_order":      "desc",
        "limit":           5,
    }
    resp = requests.get(FRED_BASE, params=params, timeout=15)
    resp.raise_for_status()
    for obs in resp.json().get("observations", []):
        if obs["value"] != ".":
            return {"value": float(obs["value"]), "observation_date": obs["date"],
                    "source": f"FRED:{series_id}"}
    raise ValueError(f"STALE_DATA: {series_id} has no data on or before {as_of}")


def fetch_spreads(fred_api_key: str) -> dict:
    """
    Fetch IG and HY OAS spreads for the most recent Friday close.
    Values returned in basis points (FRED stores as percent; multiplied × 100).

    Returns:
        {
            "IG_OAS": {"value": 81.0, "observation_date": "2026-04-17", "source": "FRED:BAMLC0A0CM"},
            "HY_OAS": {"value": 286.0, ...},
            "IG_MTD_change": -6.0,   # bps, negative = tightening
            "HY_MTD_change": -30.0,
            "week_ending": "2026-04-18",
        }
    """
    friday     = _most_recent_friday()
    month_start = _month_start()
    result     = {"week_ending": friday.isoformat()}

    for series_id, label in SPREAD_SERIES.items():
        current = _fetch_latest_on_or_before(series_id, friday, fred_api_key)
        start   = _fetch_latest_on_or_before(series_id, month_start, fred_api_key)

        # Convert percent → bps
        current_bps = round(current["value"] * 100, 1)
        start_bps   = round(start["value"]   * 100, 1)

        result[label] = {
            "value":            current_bps,
            "observation_date": current["observation_date"],
            "source":           current["source"],
        }
        mtd_key = label.replace("_OAS", "_MTD_change")
        result[mtd_key] = round(current_bps - start_bps, 1)

    return result


if __name__ == "__main__":
    import json
    load_dotenv()
    data = fetch_spreads(fred_api_key=os.environ["FRED_API_KEY"])
    print(json.dumps(data, indent=2))
