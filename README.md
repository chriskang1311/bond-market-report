# Bond Market Weekly Report

Automated fixed-income research pipeline: parallel FRED data + Tavily web search →
validated JSON payload → Claude narrative synthesis → QA fact-check → PDF report →
Gmail delivery → committed to `reports/` for embedding.

The published PDF is always at:

```
https://raw.githubusercontent.com/chriskang1311/bond-market-report/main/reports/latest.pdf
```

## Scheduling

The report runs from **GitHub Actions** — [`.github/workflows/weekly-report.yml`](.github/workflows/weekly-report.yml),
every Friday at 23:00 UTC. This replaced the Modal cron (`modal_app.py`), whose
schedule was silently disabled ~30 days after deploy on the free plan.

- **Manual run:** Actions tab → *Weekly Bond Report* → *Run workflow*.
- **Keep-alive:** GitHub disables scheduled workflows after 60 days with no repo
  activity. Each successful run commits a PDF, which counts as activity, so the
  schedule is self-sustaining once it's running.

`modal_app.py` is kept as an alternate runner but is no longer the scheduler.

## Required GitHub Actions secrets

Set these in **Settings → Secrets and variables → Actions**:

| Secret | Source |
|---|---|
| `FRED_API_KEY` | fred.stlouisfed.org (free) |
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `TAVILY_API_KEY` | app.tavily.com (free tier available) |
| `GMAIL_ADDRESS` | sender Gmail address |
| `GMAIL_APP_PASSWORD` | Google Account → Security → App Passwords |
| `RECIPIENT_EMAIL` | report destination (comma-separated for multiple) |

`GITHUB_TOKEN` is **not** a secret you set — the workflow uses the built-in token
(with `contents: write`) to commit the PDFs, so there's no personal access token
to rotate.

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env          # then fill in the values above

python run_report.py --test   # generate PDF, open locally, no email
python run_report.py          # full run: email + commit
```

Individual tools can be run standalone — see [`CLAUDE.md`](CLAUDE.md) for the full
list and the per-tool notes.
