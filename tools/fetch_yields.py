"""
tools/fetch_yields.py

Fetches treasury yields from FRED pinned to Friday close.
Raises ValueError("STALE_DATA: ...") if Friday data not yet posted.

Standalone test:
    python3 tools/fetch_yields.py
"""

import os
import ssl
import certifi
import requests
from datetime import date, timedelta
from dotenv import load_dotenv

os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

TREASURY_SERIES = {
    "DGS2":  "2yr",
    "DGS5":  "5yr",
    "DGS10": "10yr",
    "DGS20": "20yr",
    "DGS30": "30yr",
}


def _most_recent_friday() -> date:
    today = date.today()
    days_since_friday = (today.weekday() - 4) % 7
    return today - timedelta(days=days_since_friday)


def _fetch_on_or_before(series_id: str, as_of: date, api_key: str, require_exact: bool = False) -> dict:
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
            if require_exact and obs["date"] != as_of.isoformat():
                raise ValueError(f"STALE_DATA: {series_id} not posted for {as_of} (latest: {obs['date']})")
            return {"value": float(obs["value"]), "observation_date": obs["date"],
                    "source": f"FRED:{series_id}"}
    raise ValueError(f"STALE_DATA: {series_id} has no data on or before {as_of}")


def _month_start() -> date:
    today = date.today()
    return date(today.year, today.month, 1)


def _year_ago(ref: date) -> date:
    return ref.replace(year=ref.year - 1)


def fetch_yields(fred_api_key: str) -> dict:
    """
    Fetch treasury yields for the most recent Friday close, plus month-start
    and year-ago comparison values for the yield curve chart.

    Returns:
        {
            "week_ending": "2026-04-18",
            "DGS2":  {"value": 3.78, "observation_date": "2026-04-18", "source": "FRED:DGS2"},
            ...
            "month_start": {"DGS2": 3.85, "DGS5": 4.10, ...},
            "year_ago":    {"DGS2": 4.90, "DGS5": 4.70, ...},
        }
    Raises:
        ValueError: "STALE_DATA: ..." if FRED hasn't posted Friday data yet.
    """
    friday     = _most_recent_friday()
    mstart     = _month_start()
    yago       = _year_ago(friday)
    result     = {"week_ending": friday.isoformat(), "month_start": {}, "year_ago": {}}

    for series_id in TREASURY_SERIES:
        # Friday close — must be exact
        result[series_id] = _fetch_on_or_before(series_id, friday, fred_api_key, require_exact=True)
        # Month-start and year-ago — best available, no staleness guard
        try:
            result["month_start"][series_id] = _fetch_on_or_before(series_id, mstart, fred_api_key)["value"]
        except Exception:
            result["month_start"][series_id] = None
        try:
            result["year_ago"][series_id] = _fetch_on_or_before(series_id, yago, fred_api_key)["value"]
        except Exception:
            result["year_ago"][series_id] = None

    return result


if __name__ == "__main__":
    import json
    load_dotenv()
    data = fetch_yields(fred_api_key=os.environ["FRED_API_KEY"])
    print(json.dumps(data, indent=2))
