"""
modal_app.py

Modal deployment for the weekly bond market report.
Runs every Friday at 5pm ET (21:00 UTC, EDT) automatically.

Deploy:
    modal deploy modal_app.py

Test (runs immediately, sends email):
    modal run modal_app.py

Test locally without email:
    python3 run_report.py --test
"""

import modal

app = modal.App("bond-market-report")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "anthropic",
        "beautifulsoup4",
        "certifi",
        "matplotlib",
        "pandas",
        "python-dotenv",
        "reportlab",
        "requests",
        "tavily-python",
    )
    .add_local_dir(
        ".",
        remote_path="/root/app",
        ignore=["__pycache__", ".git", ".env", "*.pyc", "bond-reports", ".DS_Store"],
    )
)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("bond-report-secrets")],
    schedule=modal.Cron("0 22 * * 5"),  # 6pm EDT (UTC-4); gives FRED 1h45m buffer after 4:15pm H.15 release
    timeout=600,
)
async def weekly_bond_report():
    import sys
    sys.path.insert(0, "/root/app")

    from run_report import main
    await main(test_mode=False)


@app.local_entrypoint()
def run_now():
    """modal run modal_app.py — triggers the report immediately."""
    weekly_bond_report.remote()
