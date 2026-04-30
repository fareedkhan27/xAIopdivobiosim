"""
notifications.py — Gmail SMTP email alerts.

SMTP strategy:
  • Primary:  port 465 SSL  (smtplib.SMTP_SSL)  — works on Railway and most hosts.
  • Fallback: port 587 STARTTLS (smtplib.SMTP)  — used when SMTP_PORT is explicitly
              set to 587 via environment variable, or when the SSL attempt fails.

Set SMTP_PORT=465 (or leave unset) for Railway deployments.
Set SMTP_PORT=587 only if your mail provider requires STARTTLS.
"""

import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

SMTP_SERVER   = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", 465))   # 465 = SSL (Railway-safe default)
EMAIL_SENDER    = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD  = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", "")

_SMTP_TIMEOUT = 20  # seconds — fail fast rather than hanging


def _send_html_email(subject: str, html_body: str) -> None:
    """Low-level SMTP sender for HTML emails.

    Tries SSL (port 465) first; falls back to STARTTLS (port 587) if the
    configured port is 587 or if the SSL connection is refused.
    """
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT]):
        raise EnvironmentError(
            "EMAIL_SENDER, EMAIL_PASSWORD, and EMAIL_RECIPIENT must be set "
            "in Railway environment variables (or .env for local dev)."
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = EMAIL_RECIPIENT
    msg.attach(MIMEText(html_body, "html"))

    raw = msg.as_string()

    def _try_ssl(port: int) -> None:
        log.info("SMTP: trying SSL on %s:%d", SMTP_SERVER, port)
        with smtplib.SMTP_SSL(SMTP_SERVER, port, timeout=_SMTP_TIMEOUT) as srv:
            srv.login(EMAIL_SENDER, EMAIL_PASSWORD)
            srv.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, raw)
        log.info("SMTP: email sent via SSL (%s:%d)", SMTP_SERVER, port)

    def _try_starttls(port: int) -> None:
        log.info("SMTP: trying STARTTLS on %s:%d", SMTP_SERVER, port)
        with smtplib.SMTP(SMTP_SERVER, port, timeout=_SMTP_TIMEOUT) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(EMAIL_SENDER, EMAIL_PASSWORD)
            srv.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, raw)
        log.info("SMTP: email sent via STARTTLS (%s:%d)", SMTP_SERVER, port)

    if SMTP_PORT == 587:
        # Caller explicitly requested STARTTLS; try it, fall back to SSL 465.
        try:
            _try_starttls(587)
            return
        except Exception as e1:
            log.warning("STARTTLS on 587 failed (%s); falling back to SSL 465.", e1)
        _try_ssl(465)
    else:
        # Default: SSL on the configured port (465); fall back to STARTTLS 587.
        try:
            _try_ssl(SMTP_PORT)
            return
        except Exception as e1:
            log.warning("SSL on %d failed (%s); falling back to STARTTLS 587.", SMTP_PORT, e1)
        _try_starttls(587)


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


def send_high_risk_alert(report_data: dict) -> None:
    """Send a high-priority email listing every High-risk LR market threat.

    Only called when at least one threat has risk_level == 'High'.
    Includes full threat table (Country, Op. Model, Company, Biosimilar,
    Est. Launch, Risk Rationale, Recommended Actions) plus exec summary,
    consolidated action summary, and a direct dashboard link.
    Mobile-friendly layout using max-width and inline styles.
    """
    report_data = report_data or {}
    now = datetime.now()
    run_date = now.strftime("%d %B %Y, %H:%M UTC")
    date_short = now.strftime("%Y-%m-%d")
    subject = f"\u26a0\ufe0f HIGH-RISK Opdivo Biosimilar Threat Alert \u2013 {date_short}"

    executive_summary = report_data.get("executive_summary", "No summary available.")
    threats = report_data.get("my_markets_threat", []) or []

    high_risk = [
        t for t in threats
        if str(t.get("risk_level", "")).strip().lower() == "high"
    ]

    # ── Build one table row per High-risk threat ───────────────────────────
    threat_rows = []
    all_actions: list[str] = []   # collect unique actions for summary section

    for t in high_risk:
        country    = str(t.get("country", "Unknown")).strip()
        region     = str(t.get("region", "—")).strip()
        op_model   = str(t.get("operational_model", "—")).strip()
        company    = str(t.get("company", "Unknown")).strip()
        biosimilar = str(t.get("biosimilar", "—")).strip()
        phase      = str(t.get("phase", "—")).strip()
        est_launch = str(t.get("est_launch", "TBD")).strip()
        rationale  = str(t.get("risk_rationale", "No rationale provided.")).strip()
        actions    = t.get("recommended_actions", []) or []

        for a in actions:
            if a and a not in all_actions:
                all_actions.append(a)

        actions_html = "".join(
            f'<li style="margin-bottom:4px;color:#fcd34d;font-size:12px;">{a}</li>'
            for a in actions
        ) if actions else '<li style="color:#9ca3af;font-size:12px;">No actions specified</li>'

        # LPM = red badge, OPM = amber badge, others = grey
        if op_model.upper() == "LPM":
            badge_bg, badge_fg = "#7f1d1d", "#fca5a5"
        elif op_model.upper() == "OPM":
            badge_bg, badge_fg = "#78350f", "#fcd34d"
        else:
            badge_bg, badge_fg = "#1f2937", "#9ca3af"

        threat_rows.append(f"""
        <tr>
          <td style="padding:12px 10px;border-bottom:1px solid #374151;vertical-align:top;">
            <span style="color:#f3f4f6;font-weight:600;">{country}</span><br>
            <span style="font-size:11px;color:#9ca3af;">{region}</span>
          </td>
          <td style="padding:12px 10px;border-bottom:1px solid #374151;vertical-align:top;text-align:center;">
            <span style="background:{badge_bg};color:{badge_fg};border-radius:4px;
                         padding:3px 9px;font-size:12px;font-weight:700;white-space:nowrap;">
              {op_model}
            </span>
          </td>
          <td style="padding:12px 10px;border-bottom:1px solid #374151;vertical-align:top;
                     color:#e5e7eb;font-weight:600;">{company}</td>
          <td style="padding:12px 10px;border-bottom:1px solid #374151;vertical-align:top;color:#e5e7eb;">
            {biosimilar}<br><span style="font-size:11px;color:#9ca3af;">{phase}</span>
          </td>
          <td style="padding:12px 10px;border-bottom:1px solid #374151;vertical-align:top;
                     color:#fbbf24;font-weight:700;white-space:nowrap;">{est_launch}</td>
          <td style="padding:12px 10px;border-bottom:1px solid #374151;vertical-align:top;
                     color:#d1d5db;font-size:13px;line-height:1.5;">{rationale}</td>
          <td style="padding:12px 10px;border-bottom:1px solid #374151;vertical-align:top;">
            <ul style="margin:0;padding-left:14px;">{actions_html}</ul>
          </td>
        </tr>
        """)

    threat_table = f"""
    <div style="overflow-x:auto;">
    <table style="width:100%;min-width:680px;border-collapse:collapse;
                  background:#111827;border:1px solid #374151;
                  border-radius:10px;overflow:hidden;font-size:13px;">
      <thead>
        <tr style="background:#1f2937;">
          <th style="text-align:left;padding:10px 10px;color:#fca5a5;border-bottom:1px solid #374151;">Country</th>
          <th style="text-align:center;padding:10px 10px;color:#fca5a5;border-bottom:1px solid #374151;">Op. Model</th>
          <th style="text-align:left;padding:10px 10px;color:#fca5a5;border-bottom:1px solid #374151;">Company</th>
          <th style="text-align:left;padding:10px 10px;color:#fca5a5;border-bottom:1px solid #374151;">Biosimilar</th>
          <th style="text-align:left;padding:10px 10px;color:#fca5a5;border-bottom:1px solid #374151;">Est. Launch</th>
          <th style="text-align:left;padding:10px 10px;color:#fca5a5;border-bottom:1px solid #374151;">Risk Rationale</th>
          <th style="text-align:left;padding:10px 10px;color:#fca5a5;border-bottom:1px solid #374151;">Recommended Actions</th>
        </tr>
      </thead>
      <tbody>
        {chr(10).join(threat_rows)}
      </tbody>
    </table>
    </div>
    """

    # ── Consolidated recommended actions block ─────────────────────────────
    if all_actions:
        actions_summary_items = "".join(
            f'<li style="margin-bottom:6px;color:#fcd34d;">{a}</li>'
            for a in all_actions
        )
        actions_summary_section = f"""
        <h3 style="color:#e5e7eb;margin:22px 0 10px;">&#9989; Key Recommended Actions</h3>
        <div style="background:#1c1917;border:1px solid #78350f;border-radius:10px;
                    padding:14px 18px;color:#d1d5db;">
          <ul style="margin:0;padding-left:18px;line-height:1.8;">
            {actions_summary_items}
          </ul>
        </div>
        """
    else:
        actions_summary_section = ""

    html_body = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>High-Risk Biosimilar Alert</title>
    </head>
    <body style="margin:0;padding:0;background:#0f172a;font-family:Arial,Helvetica,sans-serif;
                 color:#f3f4f6;-webkit-text-size-adjust:100%;">
      <div style="max-width:900px;margin:24px auto;background:#111827;
                  border:2px solid #dc2626;border-radius:14px;padding:28px 24px;">

        <!-- ── Header ─────────────────────────────────────────────────── -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:4px;">
          <tr>
            <td style="vertical-align:middle;">
              <span style="font-size:26px;vertical-align:middle;">&#9888;&#65039;</span>
              <span style="font-size:20px;font-weight:700;color:#fca5a5;
                           vertical-align:middle;margin-left:8px;">
                HIGH-RISK Biosimilar Threat Alert
              </span>
            </td>
          </tr>
        </table>
        <p style="font-size:12px;color:#9ca3af;margin:4px 0 0;">
          Opdivo Surveillance &mdash; Report generated: {run_date}
        </p>

        <hr style="border:none;border-top:1px solid #374151;margin:18px 0;">

        <!-- ── Greeting ───────────────────────────────────────────────── -->
        <p style="font-size:15px;color:#e5e7eb;margin:0 0 16px;">
          Dear Operations Team,
        </p>
        <p style="font-size:14px;color:#d1d5db;margin:0 0 18px;line-height:1.6;">
          The Opdivo Biosimilar Surveillance system has detected
          <strong style="color:#f87171;">{len(high_risk)} High-risk threat(s)</strong>
          in your LR Markets during the latest automated scan.
          Immediate review and action are recommended.
        </p>

        <!-- ── KPI chips ──────────────────────────────────────────────── -->
        <table cellpadding="0" cellspacing="0" style="margin-bottom:20px;">
          <tr>
            <td style="padding-right:12px;">
              <div style="background:#450a0a;border:1px solid #dc2626;border-radius:10px;
                          padding:10px 16px;min-width:120px;display:inline-block;">
                <div style="font-size:11px;color:#fca5a5;">&#128680; High-Risk Threats</div>
                <div style="font-size:26px;font-weight:700;color:#f87171;">{len(high_risk)}</div>
              </div>
            </td>
            <td>
              <div style="background:#1f2937;border:1px solid #374151;border-radius:10px;
                          padding:10px 16px;min-width:120px;display:inline-block;">
                <div style="font-size:11px;color:#9ca3af;">Total Threats Tracked</div>
                <div style="font-size:26px;font-weight:700;color:#e5e7eb;">{len(threats)}</div>
              </div>
            </td>
          </tr>
        </table>

        <!-- ── Executive Summary ──────────────────────────────────────── -->
        <h3 style="color:#e5e7eb;margin:0 0 8px;">Executive Summary</h3>
        <div style="background:#0b1220;border:1px solid #1f2937;border-radius:10px;
                    padding:14px 16px;color:#d1d5db;line-height:1.7;font-size:14px;">
          {executive_summary}
        </div>

        <!-- ── High-Risk Threats Table ────────────────────────────────── -->
        <h3 style="color:#fca5a5;margin:22px 0 10px;">
          &#128680; High-Risk Threats &mdash; Full Detail
        </h3>
        {threat_table}

        <!-- ── Consolidated Recommended Actions ──────────────────────── -->
        {actions_summary_section}

        <!-- ── CTA ───────────────────────────────────────────────────── -->
        <div style="margin-top:26px;padding-top:18px;border-top:1px solid #374151;">
          <p style="font-size:14px;color:#d1d5db;margin:0 0 14px;">
            View the full report, trend charts, and pipeline tracker on the dashboard:
          </p>
          <a href="https://biosimintel.com"
             style="display:inline-block;background:#dc2626;color:#ffffff;
                    text-decoration:none;font-weight:700;padding:12px 22px;
                    border-radius:8px;font-size:14px;letter-spacing:0.02em;">
            &#128279;&nbsp; Open Dashboard &mdash; biosimintel.com
          </a>
          <p style="font-size:11px;color:#6b7280;margin:12px 0 0;">
            This alert was automatically generated by the Opdivo Biosimilar Surveillance system
            on {run_date}. Do not reply to this email.
          </p>
        </div>

      </div>
    </body>
    </html>
    """

    _send_html_email(subject=subject, html_body=html_body)


def send_test_email() -> None:
    """Send a test email with synthetic High-risk threat data.

    Exercises the full send_high_risk_alert() template end-to-end so the
    operations team can verify formatting and delivery without running a
    live surveillance job.
    """
    test_data: dict = {
        "executive_summary": (
            "[TEST] This is a system-generated test email from the Opdivo Biosimilar "
            "Surveillance platform. No real threats are reported. "
            "Two synthetic High-risk entries are included below to verify the email "
            "template, table rendering, and recommended actions formatting."
        ),
        "my_markets_threat": [
            {
                "country": "Brazil",
                "region": "LATAM",
                "operational_model": "LPM",
                "company": "Biocon Biologics [TEST]",
                "biosimilar": "nivolumab-bcdb [TEST]",
                "phase": "BLA Submitted",
                "est_launch": "Q3 2026",
                "risk_level": "High",
                "risk_rationale": (
                    "[TEST] Regulatory submission filed with ANVISA; "
                    "pricing 35% below Opdivo list price expected at launch."
                ),
                "recommended_actions": [
                    "Accelerate government tender contracting in Brazil",
                    "Engage key oncologists with clinical differentiation data",
                    "Prepare rapid response pricing model",
                ],
                "source": "https://example.com/test",
            },
            {
                "country": "Egypt",
                "region": "MEA",
                "operational_model": "OPM",
                "company": "Samsung Bioepis [TEST]",
                "biosimilar": "SB17 nivolumab [TEST]",
                "phase": "Phase III",
                "est_launch": "2027",
                "risk_level": "High",
                "risk_rationale": (
                    "[TEST] Phase III completion imminent; "
                    "distributor partnerships confirmed for MENA region."
                ),
                "recommended_actions": [
                    "Strengthen distributor exclusivity agreements in Egypt",
                    "Monitor Phase III readout and file regulatory objections if grounds exist",
                ],
                "source": "https://example.com/test",
            },
        ],
    }

    # Build the HTML body via send_high_risk_alert() but override the subject
    # to clearly mark it as a test.  We capture the outgoing call, swap the
    # subject, and then hand off to the real SMTP sender.
    import notifications as _self
    _captured: list[dict] = []

    def _capture(subject: str, html_body: str) -> None:  # type: ignore[misc]
        _captured.append({"subject": subject, "html_body": html_body})

    _orig = _self._send_html_email
    _self._send_html_email = _capture  # type: ignore[attr-defined]
    try:
        send_high_risk_alert(test_data)
    finally:
        _self._send_html_email = _orig  # type: ignore[attr-defined]

    if not _captured:
        raise RuntimeError("Test email body could not be generated.")

    _orig(
        subject="\U0001f9ea Test Email \u2014 Opdivo Biosimilar Surveillance Alert System",
        html_body=_captured[0]["html_body"],
    )


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
