"""
tools/upload_to_github.py

After each report run, commits the PDF to the GitHub repo under reports/.
Two files are always written:
  reports/latest.pdf              — always the most recent (stable embed URL)
  reports/bond_report_YYYYMMDD.pdf — dated archive copy

The stable URL for embedding:
  https://raw.githubusercontent.com/chriskang1311/bond-market-report/main/reports/latest.pdf
"""

import base64
import os
import requests
from datetime import date


REPO    = "chriskang1311/bond-market-report"
BRANCH  = "main"
API_BASE = f"https://api.github.com/repos/{REPO}/contents"


def _get_sha(path: str, token: str) -> str | None:
    """Return current blob SHA if file exists, else None."""
    r = requests.get(
        f"{API_BASE}/{path}",
        headers={"Authorization": f"token {token}",
                 "Accept": "application/vnd.github.v3+json"},
        timeout=15,
    )
    if r.status_code == 200:
        return r.json().get("sha")
    return None


def _put_file(path: str, content_b64: str, message: str, token: str) -> None:
    sha = _get_sha(path, token)
    body = {"message": message, "content": content_b64, "branch": BRANCH}
    if sha:
        body["sha"] = sha
    r = requests.put(
        f"{API_BASE}/{path}",
        json=body,
        headers={"Authorization": f"token {token}",
                 "Accept": "application/vnd.github.v3+json"},
        timeout=30,
    )
    r.raise_for_status()


def upload_report(pdf_path: str, github_token: str, week_ending: str | None = None) -> str:
    """
    Upload PDF to GitHub repo reports/ folder.

    Returns the stable public URL for embedding.
    """
    week = week_ending or date.today().isoformat()

    with open(pdf_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode()

    dated_name = f"bond_report_{week.replace('-', '')}.pdf"
    message    = f"Weekly bond report — {week}"

    _put_file(f"reports/latest.pdf",   content_b64, message, github_token)
    _put_file(f"reports/{dated_name}", content_b64, message, github_token)

    url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/reports/latest.pdf"
    print(f"  Uploaded to GitHub: {url}", flush=True)
    return url


if __name__ == "__main__":
    from dotenv import load_dotenv
    import json
    load_dotenv()

    pdf = "/tmp/bond_report_test.pdf"
    if not os.path.exists(pdf):
        print("No PDF at /tmp/bond_report_test.pdf — run generate_report.py first.")
    else:
        url = upload_report(pdf, os.environ["GITHUB_TOKEN"])
        print(f"Embed URL: {url}")
