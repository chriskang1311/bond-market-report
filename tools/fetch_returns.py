"""
tools/fetch_returns.py

Fetches MTD total return performance for IG and HY corporate bond indices from FRED.

Standalone test:
    python3 tools/fetch_returns.py
"""

import os
import certifi
import requests
from datetime import date, timedelta
from dotenv import load_dotenv

os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

RETURN_SERIES = {
    "BAMLCC0A0CMTRIV":   "IG Corporates",
    "BAMLHYH0A0HYM2TRIV": "HY Corporates",
}


def _most_recent_friday() -> date:
    today = date.today()
    return today - timedelta(days=(today.weekday() - 4) % 7)


def _month_start() -> date:
    today = date.today()
    return date(today.year, today.month, 1)


def _fetch_latest_on_or_before(series_id: str, as_of: date, api_key: str) -> tuple[float, str]:
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
            return float(obs["value"]), obs["date"]
    raise ValueError(f"No data for {series_id} on or before {as_of}")


def fetch_returns(fred_api_key: str) -> dict:
    """
    Fetch MTD excess returns for IG and HY corporate indices.

    Returns:
        {
            "IG Corporates": {"value": 0.79, "observation_date": "2026-04-17", "source": "FRED:BAMLCC0A0CMTRIV"},
            "HY Corporates": {...},
            "week_ending": "2026-04-18",
        }
    """
    friday      = _most_recent_friday()
    month_start = _month_start()
    result      = {"week_ending": friday.isoformat()}

    for series_id, label in RETURN_SERIES.items():
        try:
            current_val, current_date = _fetch_latest_on_or_before(series_id, friday, fred_api_key)
            start_val, _              = _fetch_latest_on_or_before(series_id, month_start, fred_api_key)
            mtd_pct = round((current_val / start_val - 1) * 100, 2) if start_val else None
            result[label] = {
                "value":            mtd_pct,
                "observation_date": current_date,
                "source":           f"FRED:{series_id}",
            }
        except Exception as e:
            print(f"  [WARN] {label}: {e}", flush=True)
            result[label] = {"value": None, "observation_date": None, "source": f"FRED:{series_id}"}

    return result


if __name__ == "__main__":
    import json
    load_dotenv()
    data = fetch_returns(fred_api_key=os.environ["FRED_API_KEY"])
    print(json.dumps(data, indent=2))
