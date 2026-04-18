"""
tools/validate_payload.py

Validates the merged data payload before synthesis occurs.
Halts the pipeline if data is stale or out of sanity range.

Standalone test:
    python3 tools/validate_payload.py
"""


def validate_payload(payload: dict) -> dict:
    """
    Validate the merged data payload.

    Checks:
    - All yield observation_dates match week_ending (STALE_DATA guard)
    - All yield values within 1.0–10.0%
    - IG OAS between 50–250 bps; HY OAS between 150–800 bps
    - fed_speakers key present (even if empty list)
    - late_breaking_events key present (even if empty list)

    Returns:
        {"valid": True}
        {"valid": False, "errors": ["STALE_DATA: DGS10 observation_date is 2026-04-17, expected 2026-04-18", ...]}
    """
    errors = []
    week_ending = payload.get("week_ending")
    yields      = payload.get("yields", {})
    spreads     = payload.get("spreads", {})

    # Yield date staleness — FRED lags 1 business day, so observation_date
    # may be Thursday when week_ending is Friday. Accept if within 3 days.
    from datetime import date as _date
    we = _date.fromisoformat(week_ending) if week_ending else None
    for series_id, data in yields.items():
        if series_id in ("week_ending", "month_start", "year_ago"):
            continue
        if not isinstance(data, dict):
            continue
        obs_date = data.get("observation_date")
        if obs_date and we:
            delta = (we - _date.fromisoformat(obs_date)).days
            if delta > 3:
                errors.append(
                    f"STALE_DATA: {series_id} observation_date is {obs_date}, "
                    f"which is {delta} days before week_ending {week_ending}"
                )

    # Yield value sanity
    for series_id, data in yields.items():
        if series_id == "week_ending" or not isinstance(data, dict):
            continue
        val = data.get("value")
        if val is not None and not (1.0 <= val <= 10.0):
            errors.append(f"RANGE_ERROR: {series_id} value {val}% is outside 1–10% range")

    # Spread sanity
    ig = spreads.get("IG_OAS", {})
    hy = spreads.get("HY_OAS", {})
    ig_val = ig.get("value") if isinstance(ig, dict) else None
    hy_val = hy.get("value") if isinstance(hy, dict) else None

    if ig_val is not None and not (50 <= ig_val <= 250):
        errors.append(f"RANGE_ERROR: IG_OAS {ig_val} bps is outside 50–250 bps range")
    if hy_val is not None and not (150 <= hy_val <= 800):
        errors.append(f"RANGE_ERROR: HY_OAS {hy_val} bps is outside 150–800 bps range")

    # Required keys
    if "fed_speakers" not in payload:
        errors.append("MISSING: fed_speakers key not present in payload")
    if "late_breaking_events" not in payload:
        errors.append("MISSING: late_breaking_events key not present in payload")

    if errors:
        return {"valid": False, "errors": errors}
    return {"valid": True}


if __name__ == "__main__":
    import json
    from datetime import date

    friday = date.today().isoformat()

    stub_pass = {
        "week_ending": friday,
        "yields": {
            "DGS2":  {"value": 3.78, "observation_date": friday, "source": "FRED:DGS2"},
            "DGS10": {"value": 4.32, "observation_date": friday, "source": "FRED:DGS10"},
            "DGS30": {"value": 4.93, "observation_date": friday, "source": "FRED:DGS30"},
        },
        "spreads": {
            "IG_OAS": {"value": 81.0, "observation_date": friday, "source": "FRED:BAMLC0A0CM"},
            "HY_OAS": {"value": 286.0, "observation_date": friday, "source": "FRED:BAMLH0A0HYM2"},
        },
        "returns": {},
        "fed_speakers": [],
        "late_breaking_events": [],
    }

    stub_fail = dict(stub_pass)
    stub_fail["yields"] = dict(stub_pass["yields"])
    stub_fail["yields"]["DGS10"] = {"value": 4.32, "observation_date": "2026-04-17", "source": "FRED:DGS10"}

    print("PASS test:", json.dumps(validate_payload(stub_pass), indent=2))
    print("FAIL test:", json.dumps(validate_payload(stub_fail), indent=2))
