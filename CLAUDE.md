# Agent Instructions

You're working inside the **WAT framework** (Workflows, Agents, Tools). This architecture separates concerns so that probabilistic AI handles reasoning while deterministic code handles execution. That separation is what makes this system reliable.

## The WAT Architecture

**Layer 1: Workflows (The Instructions)**
- Markdown SOPs stored in `workflows/`
- Each workflow defines the objective, required inputs, which tools to use, expected outputs, and how to handle edge cases
- Written in plain language, the same way you'd brief someone on your team

**Layer 2: Agents (The Decision-Maker)**
- This is your role. You're responsible for intelligent coordination.
- Read the relevant workflow, run tools in the correct sequence, handle failures gracefully, and ask clarifying questions when needed
- You connect intent to execution without trying to do everything yourself
- Example: If you need to pull data from a website, don't attempt it directly. Read `workflows/scrape_website.md`, figure out the required inputs, then execute `tools/scrape_single_site.py`

**Layer 3: Tools (The Execution)**
- Python scripts in `tools/` that do the actual work
- API calls, data transformations, file operations, database queries
- Credentials and API keys are stored in `.env`
- These scripts are consistent, testable, and fast

**Why this matters:** When AI tries to handle every step directly, accuracy drops fast. If each step is 90% accurate, you're down to 59% success after just five steps. By offloading execution to deterministic scripts, you stay focused on orchestration and decision-making where you excel.

## How to Operate

**1. Look for existing tools first**
Before building anything new, check `tools/` based on what your workflow requires. Only create new scripts when nothing exists for that task.

**2. Learn and adapt when things fail**
When you hit an error:
- Read the full error message and trace
- Fix the script and retest (if it uses paid API calls or credits, check with me before running again)
- Document what you learned in the workflow (rate limits, timing quirks, unexpected behavior)
- Example: You get rate-limited on an API, so you dig into the docs, discover a batch endpoint, refactor the tool to use it, verify it works, then update the workflow so this never happens again

**3. Keep workflows current**
Workflows should evolve as you learn. When you find better methods, discover constraints, or encounter recurring issues, update the workflow. That said, don't create or overwrite workflows without asking unless I explicitly tell you to. These are your instructions and need to be preserved and refined, not tossed after one use.

## The Self-Improvement Loop

Every failure is a chance to make the system stronger:
1. Identify what broke
2. Fix the tool
3. Verify the fix works
4. Update the workflow with the new approach
5. Move on with a more robust system

This loop is how the framework improves over time.

## File Structure

**What goes where:**
- **Deliverables**: Final outputs go to cloud services (Google Sheets, Slides, etc.) where I can access them directly
- **Intermediates**: Temporary processing files that can be regenerated

**Directory layout:**
```
.tmp/           # Temporary files (scraped data, intermediate exports). Regenerated as needed.
tools/          # Python scripts for deterministic execution
workflows/      # Markdown SOPs defining what to do and how
.env            # API keys and environment variables (NEVER store secrets anywhere else)
credentials.json, token.json  # Google OAuth (gitignored)
```

**Core principle:** Local files are just for processing. Anything I need to see or use lives in cloud services. Everything in `.tmp/` is disposable.

## Bottom Line

You sit between what I want (workflows) and what actually gets done (tools). Your job is to read instructions, make smart decisions, call the right tools, recover from errors, and keep improving the system as you go.

Stay pragmatic. Stay reliable. Keep learning.

---

# Bond Market Weekly Report Project

WAT-structured pipeline: parallel FRED data + Tavily web search → validated JSON payload → Claude narrative synthesis → QA fact-check → PDF report → Gmail delivery. Scheduled every Friday at 5pm ET via Claude Code cron.

## How to run

```bash
pip3 install -r requirements.txt      # once

# Test each tool individually:
python3 tools/fetch_yields.py         # Friday-pinned Treasury yields from FRED
python3 tools/fetch_spreads.py        # IG/HY OAS from FRED (bps)
python3 tools/fetch_returns.py        # MTD total returns from FRED
python3 tools/fetch_fed_speakers.py   # Fed official statements via Tavily
python3 tools/fetch_geopolitical.py   # Macro/geopolitical events via Tavily
python3 tools/validate_payload.py     # Validates merged JSON payload
python3 tools/synthesize_narrative.py # Generates intro + bullets via Claude
python3 tools/qa_narrative.py         # Fact-checks narrative against payload
python3 tools/generate_report.py      # Opens PDF in Preview
python3 tools/send_email.py           # Sends test email

# Full end-to-end:
python3 run_report.py --test          # generates PDF, opens locally
python3 run_report.py                 # full run, sends email
```

## File structure

```
run_report.py                    — Orchestrator: asyncio parallel fetch → validate → synthesize → QA → PDF → email
tools/fetch_yields.py            — Treasury yields pinned to Friday close (FRED H.15)
tools/fetch_spreads.py           — IG/HY OAS in bps, MTD change (FRED)
tools/fetch_returns.py           — MTD total returns for IG/HY (FRED)
tools/fetch_fed_speakers.py      — Fed official statements this week (Tavily + Claude parse)
tools/fetch_geopolitical.py      — Geopolitical/macro events affecting bonds (Tavily + Claude parse)
tools/validate_payload.py        — Sanity checks before synthesis (date pinning, range checks)
tools/synthesize_narrative.py    — Claude generates editorial intro + 5-7 detailed bullets
tools/qa_narrative.py            — Claude fact-checks every figure against payload; triggers retry
tools/generate_report.py         — Yield curve + excess returns charts + IR+M-style PDF
tools/send_email.py              — Gmail SMTP delivery (App Password auth)
workflows/bond_report_workflow.md — Full SOP: setup, sequence, failure handling
```

## .env variables

| Variable | Source |
|---|---|
| `FRED_API_KEY` | fred.stlouisfed.org (free) |
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `TAVILY_API_KEY` | app.tavily.com (free tier available) |
| `GMAIL_ADDRESS` | your Gmail |
| `GMAIL_APP_PASSWORD` | Google Account → Security → App Passwords |
| `RECIPIENT_EMAIL` | report destination (comma-separated for multiple) |

## FRED series

| ID | Description |
|---|---|
| `DGS2/5/10/20/30` | Treasury yields (daily, H.15) |
| `BAMLC0A0CM` | IG Corporate OAS (percent → ×100 for bps) |
| `BAMLH0A0HYM2` | HY Corporate OAS (percent → ×100 for bps) |
| `BAMLCC0A0CMTRIV` | IG Corp Total Return Index |
| `BAMLHYH0A0HYM2TRIV` | HY Corp Total Return Index |

## Colors: navy `#1B2A4A`, amber `#E8820C`, teal `#2E8B8B`, alt-row `#F5F5F5`
