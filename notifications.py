"""
notifications.py — Gmail SMTP email alerts.
"""

import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", "")


def _send_html_email(subject: str, html_body: str) -> None:
    """Low-level SMTP sender for HTML emails."""
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT]):
        raise EnvironmentError(
            "EMAIL_SENDER, EMAIL_PASSWORD, and EMAIL_RECIPIENT must be set in .env"
        )

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


def send_report_ready_email(report_data: dict) -> None:
    """Send professional report-ready alert with key operational highlights."""
    report_data = report_data or {}
    run_date = datetime.now().strftime("%Y-%m-%d")
    subject = f"Opdivo Biosimilar Surveillance Report - {run_date}"

    executive_summary = report_data.get("executive_summary", "No summary available.")
    threats = report_data.get("my_markets_threat", []) or []
    companies = report_data.get("companies", []) or []
    verified_updates = report_data.get("verified_updates", []) or []

    # KPIs for quick operational triage
    high_risk = [
        t for t in threats
        if str(t.get("risk_level", "")).strip().lower() == "high"
    ]
    launched = [
        c for c in companies
        if "launch" in str(c.get("phase", "")).lower()
    ]

    # Focus the alert on LR markets
    lr_regions = ["CEE/EU", "LATAM", "MEA"]
    high_risk_rows = []
    for threat in high_risk:
        country = str(threat.get("country", "")).strip() or "Unknown"
        if not any(region.lower() in country.lower() for region in lr_regions):
            # Keep only explicit LR-market entries when possible.
            continue
        competitor = str(threat.get("competitor", "Unknown"))
        launch = str(threat.get("expected_launch", "TBD"))
        rationale = str(threat.get("risk_rationale", "No rationale provided."))
        high_risk_rows.append(
            f"""
            <tr>
              <td style=\"padding:10px;border-bottom:1px solid #374151;color:#e5e7eb;\">{country}</td>
              <td style=\"padding:10px;border-bottom:1px solid #374151;color:#e5e7eb;\">{competitor}</td>
              <td style=\"padding:10px;border-bottom:1px solid #374151;color:#e5e7eb;\">{launch}</td>
              <td style=\"padding:10px;border-bottom:1px solid #374151;color:#9ca3af;\">{rationale}</td>
            </tr>
            """
        )

    if not high_risk_rows:
        high_risk_section = """
        <div style="background:#052e16;border:1px solid #166534;border-radius:10px;padding:14px 16px;color:#bbf7d0;">
          No High-risk threats were identified in LR Markets (CEE/EU, LATAM, MEA) in this run.
        </div>
        """
    else:
        high_risk_section = f"""
        <table style="width:100%;border-collapse:collapse;background:#111827;border:1px solid #374151;border-radius:10px;overflow:hidden;">
          <thead>
            <tr style="background:#1f2937;">
              <th style="text-align:left;padding:10px;color:#a7f3d0;border-bottom:1px solid #374151;">Market</th>
              <th style="text-align:left;padding:10px;color:#a7f3d0;border-bottom:1px solid #374151;">Competitor</th>
              <th style="text-align:left;padding:10px;color:#a7f3d0;border-bottom:1px solid #374151;">Expected Launch</th>
              <th style="text-align:left;padding:10px;color:#a7f3d0;border-bottom:1px solid #374151;">Rationale</th>
            </tr>
          </thead>
          <tbody>
            {"".join(high_risk_rows)}
          </tbody>
        </table>
        """

    html_body = f"""
    <html>
    <body style="font-family:Arial,sans-serif;background:#0f172a;color:#f3f4f6;padding:24px;">
      <div style="max-width:760px;margin:0 auto;background:#111827;border:1px solid #374151;border-radius:14px;padding:28px;">
        <h2 style="color:#34d399;margin-top:0;margin-bottom:8px;">Opdivo Biosimilar Surveillance Report</h2>
        <p style="font-size:13px;color:#9ca3af;margin-top:0;">Generated on {run_date}</p>

        <div style="display:flex;gap:10px;flex-wrap:wrap;margin:18px 0 20px;">
          <div style="background:#1f2937;border:1px solid #374151;border-radius:10px;padding:10px 12px;min-width:140px;">
            <div style="font-size:12px;color:#9ca3af;">Threats tracked</div>
            <div style="font-size:22px;font-weight:700;color:#f3f4f6;">{len(threats)}</div>
          </div>
          <div style="background:#1f2937;border:1px solid #374151;border-radius:10px;padding:10px 12px;min-width:140px;">
            <div style="font-size:12px;color:#9ca3af;">High-risk LR threats</div>
            <div style="font-size:22px;font-weight:700;color:#fda4af;">{len(high_risk_rows)}</div>
          </div>
          <div style="background:#1f2937;border:1px solid #374151;border-radius:10px;padding:10px 12px;min-width:140px;">
            <div style="font-size:12px;color:#9ca3af;">Launched biosimilars</div>
            <div style="font-size:22px;font-weight:700;color:#86efac;">{len(launched)}</div>
          </div>
          <div style="background:#1f2937;border:1px solid #374151;border-radius:10px;padding:10px 12px;min-width:140px;">
            <div style="font-size:12px;color:#9ca3af;">Key verified updates</div>
            <div style="font-size:22px;font-weight:700;color:#93c5fd;">{len(verified_updates)}</div>
          </div>
        </div>

        <h3 style="color:#e5e7eb;margin-bottom:8px;">Executive Summary</h3>
        <div style="background:#0b1220;border:1px solid #1f2937;border-radius:10px;padding:14px 16px;color:#d1d5db;line-height:1.65;">
          {executive_summary}
        </div>

        <h3 style="color:#e5e7eb;margin:18px 0 8px;">High-risk LR Markets Focus</h3>
        {high_risk_section}

        <div style="margin-top:22px;padding-top:14px;border-top:1px solid #374151;">
          <a href="https://biosimintel.com" style="display:inline-block;background:#10b981;color:#052e16;text-decoration:none;font-weight:700;padding:10px 14px;border-radius:8px;">
            Open Dashboard
          </a>
          <p style="font-size:12px;color:#6b7280;margin-top:10px;">
            Direct link: https://biosimintel.com
          </p>
        </div>
      </div>
    </body>
    </html>
    """

    _send_html_email(subject=subject, html_body=html_body)


def send_email_alert(executive_summary: str, subject: str = "🔔 New Opdivo Biosimilar Report Ready") -> None:
    """Backward-compatible wrapper for legacy calls."""
    report_data = {
        "executive_summary": executive_summary,
        "my_markets_threat": [],
        "companies": [],
        "verified_updates": [],
    }
    # Respect explicit subject only for legacy callers.
    if subject and subject != "🔔 New Opdivo Biosimilar Report Ready":
        run_date = datetime.now().strftime("%Y-%m-%d")
        report_subject = subject.replace("[Date]", run_date)
        _send_html_email(
            subject=report_subject,
            html_body=f"<html><body><p>{executive_summary}</p></body></html>",
        )
        return

    send_report_ready_email(report_data)
