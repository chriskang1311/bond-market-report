"""
tools/send_email.py

Sends the bond market PDF report via Gmail SMTP (App Password auth).

Standalone test:
    python tools/send_email.py
"""

import os
import smtplib
from datetime import date, timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _week_of_label() -> str:
    today  = date.today()
    monday = today - timedelta(days=today.weekday())
    return monday.strftime("%-B %-d, %Y")


def send_email(
    pdf_path: str,
    gmail_address: str,
    app_password: str,
    recipient_email: str,
) -> None:
    """
    Send the bond market PDF report via Gmail SMTP.

    Args:
        pdf_path:        Absolute path to the PDF file
        gmail_address:   Sender Gmail address
        app_password:    Gmail App Password (16 chars, from Google Account → Security)
        recipient_email: Destination email address
    """
    subject = f"US Bond Market Weekly Update \u2014 Week of {_week_of_label()}"
    body = (
        "Please find attached this week's US Bond Market report.\n\n"
        "Data sourced from FRED, MarketWatch, CNBC, and Reuters."
    )

    # Support comma-separated recipient list
    recipients = [r.strip() for r in recipient_email.split(",") if r.strip()]

    msg            = MIMEMultipart()
    msg["From"]    = gmail_address
    msg["To"]      = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with open(pdf_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition",
                    f'attachment; filename="{os.path.basename(pdf_path)}"')
    msg.attach(part)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.login(gmail_address, app_password)
        server.sendmail(gmail_address, recipients, msg.as_string())

    print(f"  Email sent to {', '.join(recipients)}", flush=True)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    # Requires a real PDF to exist — run generate_report.py first
    pdf = "/tmp/bond_report_test.pdf"
    if not os.path.exists(pdf):
        print(f"No PDF at {pdf} — run 'python tools/generate_report.py' first.")
    else:
        send_email(
            pdf_path=pdf,
            gmail_address=os.environ["GMAIL_ADDRESS"],
            app_password=os.environ["GMAIL_APP_PASSWORD"],
            recipient_email=os.environ["RECIPIENT_EMAIL"],
        )
