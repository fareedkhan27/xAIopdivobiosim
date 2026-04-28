"""
notifications.py — Gmail SMTP email alerts.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", "")


def send_email_alert(executive_summary: str, subject: str = "🔔 New Opdivo Biosimilar Report Ready") -> None:
    """Send an HTML email with the executive summary."""
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT]):
        raise EnvironmentError(
            "EMAIL_SENDER, EMAIL_PASSWORD, and EMAIL_RECIPIENT must be set in .env"
        )

    html_body = f"""
    <html>
    <body style="font-family:Arial,sans-serif;background:#111827;color:#f3f4f6;padding:24px;">
      <div style="max-width:600px;margin:0 auto;background:#1f2937;border-radius:12px;padding:32px;">
        <h2 style="color:#00D4C8;margin-top:0;">Opdivo Biosimilar Surveillance</h2>
        <p style="font-size:14px;color:#9ca3af;">A new automated surveillance report has been generated.</p>
        <hr style="border-color:#374151;" />
        <h3 style="color:#f3f4f6;">Executive Summary</h3>
        <p style="line-height:1.7;">{executive_summary}</p>
        <hr style="border-color:#374151;" />
        <p style="font-size:12px;color:#6b7280;">
          Open your Streamlit dashboard to view the full report, Pipeline Tracker, Social Noise, and AI Insights.
        </p>
      </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECIPIENT
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
