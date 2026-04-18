"""
run_report.py

Weekly bond market report orchestrator.
Runs the full pipeline: parallel data collection → validation → synthesis → QA → PDF → email.

Usage:
    python3 run_report.py           # full run, sends email
    python3 run_report.py --test    # generates PDF, opens locally, no email

Scheduling:
    Set up via Claude Code's /schedule skill to run every Friday at 5pm ET.
"""

import argparse
import asyncio
import os
import subprocess
import sys
from datetime import date, timedelta
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.fetch_yields       import fetch_yields
from tools.fetch_spreads      import fetch_spreads
from tools.fetch_returns      import fetch_returns
from tools.fetch_fed_speakers import fetch_fed_speakers
from tools.fetch_geopolitical import fetch_geopolitical
from tools.validate_payload   import validate_payload
from tools.synthesize_narrative import synthesize_narrative
from tools.qa_narrative       import qa_narrative
from tools.generate_report    import generate_report
from tools.send_email         import send_email


def _most_recent_friday() -> date:
    today = date.today()
    return today - timedelta(days=(today.weekday() - 4) % 7)


async def main(test_mode: bool = False) -> None:
    load_dotenv()

    fred_api_key    = os.environ["FRED_API_KEY"]
    anthropic_key   = os.environ["ANTHROPIC_API_KEY"]
    tavily_key      = os.environ["TAVILY_API_KEY"]
    gmail_address   = os.environ["GMAIL_ADDRESS"]
    app_password    = os.environ["GMAIL_APP_PASSWORD"]
    recipient_email = os.environ["RECIPIENT_EMAIL"]

    friday = _most_recent_friday()

    print("=" * 55, flush=True)
    print(f"US Bond Market Report — week ending {friday}", flush=True)
    print("=" * 55, flush=True)

    # ── Step 1: Parallel data collection ─────────────────────────────────────
    print("\n[1/5] Collecting data in parallel...", flush=True)
    results = await asyncio.gather(
        asyncio.to_thread(fetch_yields,       fred_api_key),
        asyncio.to_thread(fetch_spreads,      fred_api_key),
        asyncio.to_thread(fetch_returns,      fred_api_key),
        asyncio.to_thread(fetch_fed_speakers, tavily_key, anthropic_key),
        asyncio.to_thread(fetch_geopolitical, tavily_key, anthropic_key),
        return_exceptions=True,
    )

    yields_data, spreads_data, returns_data, speakers, geo_events = results

    for name, r in zip(["yields", "spreads", "returns", "fed_speakers", "geopolitical"], results):
        if isinstance(r, Exception):
            print(f"  [ERROR] {name}: {r}", flush=True)
            if "STALE_DATA" in str(r):
                print("  Stale data detected — aborting. Retry after FRED H.15 posts.", flush=True)
            sys.exit(1)

    print(f"  Yields: {len([k for k in yields_data if k not in ('week_ending','month_start','year_ago')])} series", flush=True)
    print(f"  Fed speakers: {len(speakers)}", flush=True)
    print(f"  Geopolitical events: {len(geo_events)}", flush=True)

    # ── Step 2: Merge payload ─────────────────────────────────────────────────
    payload = {
        "week_ending":          friday.isoformat(),
        "yields":               yields_data,
        "spreads":              spreads_data,
        "returns":              returns_data,
        "fed_speakers":         speakers,
        "late_breaking_events": geo_events,
    }

    # ── Step 3: Validate ──────────────────────────────────────────────────────
    print("\n[2/5] Validating payload...", flush=True)
    v = validate_payload(payload)
    if not v["valid"]:
        print(f"  [ERROR] Validation failed:", flush=True)
        for err in v["errors"]:
            print(f"    • {err}", flush=True)
        sys.exit(1)
    print("  Payload valid.", flush=True)

    # ── Step 4: Synthesize + QA retry loop ───────────────────────────────────
    print("\n[3/5] Synthesizing narrative...", flush=True)
    narrative = synthesize_narrative(payload, anthropic_key)
    bullet_count = len(narrative.get("bullets", []))
    print(f"  Generated intro + {bullet_count} bullets.", flush=True)

    qa_passed = False
    for attempt in range(1, 3):
        print(f"\n[3/5] QA check (attempt {attempt}/2)...", flush=True)
        qa = qa_narrative(narrative, payload, anthropic_key)
        if qa["status"] == "PASS":
            print("  QA passed.", flush=True)
            qa_passed = True
            break
        print(f"  QA failed — {len(qa['failures'])} issues. Retrying synthesis...", flush=True)
        for f in qa["failures"]:
            print(f"    • {f}", flush=True)
        narrative = synthesize_narrative(payload, anthropic_key, qa_failures=qa["failures"])

    if not qa_passed:
        narrative.setdefault("bullets", []).append({
            "text": "\u26a0\ufe0f QA flags present \u2014 human review required before trusting figures.",
            "sub_bullets": [],
        })
        print("  QA did not pass after 2 attempts. Proceeding with warning bullet.", flush=True)

    # ── Step 5: Generate PDF ─────────────────────────────────────────────────
    print("\n[4/5] Building PDF...", flush=True)
    report_dir = os.path.expanduser("~/bond-reports")
    os.makedirs(report_dir, exist_ok=True)
    pdf_path = os.path.join(report_dir, f"bond_report_{friday.strftime('%Y%m%d')}.pdf")
    generate_report(payload, narrative, pdf_path)
    size_kb = os.path.getsize(pdf_path) // 1024
    print(f"  PDF saved ({size_kb} KB): {pdf_path}", flush=True)

    # ── Step 6: Deliver ───────────────────────────────────────────────────────
    print("\n[5/5] Delivering report...", flush=True)
    if test_mode:
        print("  [TEST MODE] Opening PDF locally.", flush=True)
        subprocess.run(["open", pdf_path])
    else:
        send_email(pdf_path, gmail_address, app_password, recipient_email)

    print(f"\n{'=' * 55}", flush=True)
    print("Done.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Weekly bond market report")
    parser.add_argument("--test", action="store_true",
                        help="Open PDF locally instead of sending email")
    asyncio.run(main(test_mode=parser.parse_args().test))
