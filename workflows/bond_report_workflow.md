# Bond Market Report Workflow

## Objective

Generate and deliver a weekly PDF bond market summary every Thursday at 5pm ET. The report covers treasury yield curve shifts, month-to-date excess returns by sector, IG/HY credit spreads, and 5-7 news-driven bullet points synthesized by Claude.

## Required Secrets

All stored in Modal under secret name `bond-report-secrets` AND mirrored in `.env` for local dev.

| Key | Source | Notes |
|-----|--------|-------|
| `FRED_API_KEY` | fred.stlouisfed.org (free account) | Instant via email |
| `ANTHROPIC_API_KEY` | console.anthropic.com | Powers bullet synthesis |
| `GMAIL_ADDRESS` | Your Gmail address | Must match App Password account |
| `GMAIL_APP_PASSWORD` | Google Account → Security → App Passwords | 16-char code; requires 2FA enabled |
| `RECIPIENT_EMAIL` | Report destination address | Single address |

## Execution Sequence

```
1. tools/fetch_fred_data.py
   - Initializes FRED client with FRED_API_KEY
   - Fetches 5 treasury yields (2/5/10/20/30yr): current, month-start, year-ago
   - Fetches IG OAS (BAMLC0A0CM) and HY OAS (BAMLH0A0HYM2): current + MTD change
   - Fetches 6 total return index series for MTD excess return calc
   - Returns: {yield_data, spreads_data, returns_data, as_of}

2. tools/scrape_news.py
   - Scrapes headlines from CNBC bonds, MarketWatch bonds, Reuters rates-bonds
   - Filters for bond-relevant keywords (treasury, fed, yield, spread, credit, etc.)
   - Passes up to 10 articles + full FRED market data to claude-sonnet-4-6
   - Claude returns 5-7 factual bullet points citing specific numbers
   - Falls back to data-only synthesis if scraping fails

3. tools/generate_report.py
   - Generates yield curve PNG (3 lines: current/month-start/year-ago)
   - Generates MTD excess returns horizontal bar chart PNG (6 sectors)
   - Assembles reportlab PDF (8.5×11):
       • Header: navy bar with week date range in amber
       • Section 1: bullet points in orange-bordered box
       • Section 2: two-column — yield curve + yield table | excess returns chart
       • Section 3: credit spreads table (IG OAS, HY OAS, MTD change)
       • Footer: sources, data date, page number
   - Saves PDF to /tmp/bond_report_YYYYMMDD.pdf

4. tools/send_email.py
   - Authenticates to Gmail SMTP (smtp.gmail.com:587) via App Password
   - Subject: "US Bond Market Weekly Update — Week of [Monday date]"
   - Attaches PDF and sends to RECIPIENT_EMAIL
```

## One-Time Setup

### Step 1: Get API Keys (do this outside Claude Code)

1. **FRED API key**: Go to fred.stlouisfed.org → register → API Keys tab. Arrives instantly by email.
2. **Anthropic API key**: Go to console.anthropic.com → API Keys → Create.
3. **Gmail App Password**:
   - Go to myaccount.google.com → Security → 2-Step Verification (must be enabled first)
   - Then Security → App Passwords → Create new → name it "Bond Report"
   - Copy the 16-character password immediately (shown once)

### Step 2: Fill in `.env` for local testing

```
FRED_API_KEY=your_fred_key
ANTHROPIC_API_KEY=your_anthropic_key
GMAIL_ADDRESS=you@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
RECIPIENT_EMAIL=you@gmail.com
```

### Step 3: Install dependencies and test each tool

```bash
pip install -r requirements.txt

# Test 1: FRED data fetch (prints JSON of all market data)
python tools/fetch_fred_data.py

# Test 2: News scrape + Claude bullets (uses stub market data)
python tools/scrape_news.py

# Test 3: PDF generation (opens /tmp/bond_report_test.pdf)
python tools/generate_report.py

# Test 4: Email send (requires Test 3 PDF to exist)
python tools/send_email.py
```

### Step 4: Deploy to Modal

```bash
# Install Modal
pip install modal

# Authenticate (opens browser once)
modal token new

# Create secret in Modal dashboard:
# Go to modal.com > Secrets > Create New Secret > Custom
# Name: bond-report-secrets
# Add all 5 keys from the table above

# Deploy
modal deploy modal_app.py

# End-to-end test (runs full pipeline immediately)
modal run modal_app.py
```

Verify the schedule at modal.com > Apps > bond-market-report > Schedule tab.

## Testing Checklist

Before relying on the Thursday cron, verify each component passes:

- [ ] `python tools/fetch_fred_data.py` — prints non-null yields and spreads
- [ ] `python tools/scrape_news.py` — prints 5-7 bullet points
- [ ] `python tools/generate_report.py` — PDF opens correctly in Preview
- [ ] `python tools/send_email.py` — email arrives with PDF attached
- [ ] `modal run modal_app.py` — full end-to-end run via Modal

## Failure Handling

| Stage | Failure | Resolution |
|-------|---------|-----------|
| FRED | Series returns empty | FRED occasionally has 1-2 day lag. Tool logs `[WARN]` and continues with None values. |
| FRED | `FRED_API_KEY` invalid | Check secret. Free key has no rate limit for this use case. |
| Scraper | Site blocks request | Tool skips that source, logs `[WARN]`. Other sources continue. |
| Scraper | All sources fail | Falls back to Claude synthesis using FRED data only. Still produces bullets. |
| Claude | Overloaded (529) | Modal will retry once after 30s. If persistent, check status.anthropic.com. |
| PDF | `reportlab` error | Usually a missing font or `None` value in chart data. Check `[WARN]` logs above. |
| Gmail | Auth failure | App Password expired or revoked. Re-generate in Google Account → App Passwords and update Modal secret. |
| Gmail | `SMTP` timeout | Transient. Modal retry handles it. |
| Modal | Secret missing | `KeyError` in logs. Add the missing key to `bond-report-secrets` in Modal dashboard. |
| Modal | Container timeout | 5-min limit. Typical run is ~90s. If hitting limit, check for slow FRED or Claude calls. |

## Known Constraints

- **Cron timing**: `0 21 * * 4` = Thursday 9pm UTC = 5pm EDT (summer). During EST (winter, Nov–Mar), this becomes 4pm ET. Adjust to `0 22 * * 4` in winter if you want strict 5pm ET year-round.
- **FRED data lag**: Treasury yields are usually available same-day by 4pm ET. Spreads can lag 1 business day.
- **MORTGAGE30US proxy**: The Agency MBS sector uses the 30-year mortgage rate as a level proxy, not a true total return index. MTD return is an approximation.
- **Sector proxies**: IG Financials/Industrials/Utilities use ICE BofA AAA/A/BBB indices as proxies, noted with `*` in the report.
- **Claude model**: `claude-sonnet-4-6`. Typical cost per run: ~$0.01–0.03 for the bullet synthesis call.

## Updating the Report

- **Add FRED series**: Edit `EXCESS_RETURN_SECTORS` in `tools/fetch_fred_data.py`
- **Change Claude model**: Edit `model=` in `tools/scrape_news.py`
- **Change PDF layout/colors**: Edit constants and `generate_report()` in `tools/generate_report.py`
- **Change cron schedule**: Edit `schedule=modal.Cron(...)` in `modal_app.py`, then `modal deploy modal_app.py`
- **Add recipient**: Update `RECIPIENT_EMAIL` in Modal secret (currently single address — extend `send_email` for multiple if needed)
