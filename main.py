"""
main.py — Streamlit dashboard for the Opdivo Biosimilar Surveillance Tool.

Tabs:
  1. Dashboard Overview
  2. Pipeline Tracker
  3. Verified Intelligence
  4. Social Noise
  5. AI Insights
  6. Timeline
  7. History

Run with:  streamlit run main.py
"""

import json
import threading
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from db import get_all_reports, get_latest_report, init_db

# ─── Page config ─────────────────────────────────────────────────────────────
# MUST be the very first Streamlit call in the script.
st.set_page_config(
    page_title="Opdivo Biosimilar Surveillance",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Database initialisation ─────────────────────────────────────────────────
# Called unconditionally on every startup — CREATE TABLE IF NOT EXISTS makes it
# fully idempotent (safe to run on every rerun, no-ops if tables already exist).
import logging as _logging
_logging.basicConfig(level=_logging.INFO)
_log = _logging.getLogger(__name__)
try:
    init_db()
    _log.info("Database initialized successfully.")
except Exception as _db_err:
    _log.error("Database initialization failed: %s", _db_err)
    st.error(f"⚠️ Database error: {_db_err}. Please contact support.")
    st.stop()

# ─── Session-state bootstrap (must come before ANY other code) ────────────────
# Initialise every key we rely on so they always exist, even on a fresh session.
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "surveillance_running" not in st.session_state:
    st.session_state["surveillance_running"] = False
if "run_status" not in st.session_state:
    st.session_state["run_status"] = ""
if "job_start_time" not in st.session_state:
    st.session_state["job_start_time"] = None
if "last_report" not in st.session_state:
    # Load once from DB on first visit; subsequent reruns use the cached copy
    # unless explicitly invalidated (e.g. after a completed job).
    st.session_state["last_report"] = get_latest_report()

# ─── Password gate ────────────────────────────────────────────────────────────
# Checked immediately after session state is ready — before CSS, DB, or any UI.
_CORRECT_PASSWORD = "lrbiosim"

if not st.session_state["authenticated"]:
    # Inject minimal CSS so the login card renders correctly even though the
    # full stylesheet hasn't loaded yet.
    st.markdown("""
    <style>
    html, body, [class*="css"] {
        background-color: #111827 !important;
        color: #f3f4f6 !important;
        font-family: 'Inter', 'Segoe UI', sans-serif;
    }
    .stButton > button {
        background: #00D4C8 !important;
        color: #111827 !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        border: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="display:flex;flex-direction:column;align-items:center;
                justify-content:center;min-height:65vh;">
      <div style="background:#1f2937;border:1px solid #374151;border-radius:16px;
                  padding:48px 56px;max-width:420px;width:100%;text-align:center;
                  box-shadow:0 8px 32px rgba(0,0,0,0.5);">
        <div style="font-size:3rem;margin-bottom:10px;">💊</div>
        <h2 style="color:#f9fafb;margin:0 0 6px 0;font-size:1.55rem;font-weight:700;">
          Opdivo Biosimilar Intelligence
        </h2>
        <p style="color:#6b7280;font-size:0.82rem;margin:0 0 6px 0;
                  letter-spacing:0.04em;text-transform:uppercase;">biosimintel.com</p>
        <p style="color:#9ca3af;font-size:0.88rem;margin:0 0 32px 0;line-height:1.5;">
          Restricted access &mdash; authorised BMS personnel only.
        </p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    _col_l, _col_c, _col_r = st.columns([1, 2, 1])
    with _col_c:
        _pwd = st.text_input(
            "Access Code",
            type="password",
            placeholder="Enter access code\u2026",
            label_visibility="collapsed",
            key="login_pwd_input",
        )
        _login_btn = st.button(
            "\U0001f513 Enter Dashboard",
            use_container_width=True,
            type="primary",
            key="login_btn",
        )
        if _login_btn or _pwd:
            if _pwd == _CORRECT_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            elif _pwd:
                st.error("Incorrect access code. Please try again.")
    # Hard stop — nothing below this line renders until authenticated.
    st.stop()

# ─── Custom CSS (dark-mode biotech theme) ─────────────────────────────────────
st.markdown("""
<style>
/* ---- Base ---- */
html, body, [class*="css"] {
    background-color: #111827 !important;
    color: #f3f4f6 !important;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
/* ---- Sidebar ---- */
section[data-testid="stSidebar"] {
    background-color: #1f2937 !important;
    border-right: 1px solid #374151;
}
/* ---- Cards ---- */
.kpi-card {
    background: #1f2937;
    border: 1px solid #374151;
    border-radius: 12px;
    padding: 20px 24px;
    text-align: center;
}
.kpi-value { font-size: 2.2rem; font-weight: 700; color: #00D4C8; }
.kpi-label { font-size: 0.85rem; color: #9ca3af; margin-top: 4px; }
/* ---- Update cards ---- */
.update-card {
    background: #1f2937;
    border-left: 4px solid #00D4C8;
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 12px;
}
.update-card .source { font-size: 0.78rem; color: #9ca3af; }
.update-card .title  { font-weight: 600; margin: 4px 0; color: #f3f4f6; }
.update-card .body   { font-size: 0.9rem; color: #d1d5db; }
/* ---- Social post cards ---- */
.post-card {
    background: #1f2937;
    border: 1px solid #374151;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 10px;
}
.post-card .user  { font-weight: 600; color: #3B82F6; }
.post-card .time  { font-size: 0.78rem; color: #6b7280; margin-left: 8px; }
.post-card .text  { margin-top: 8px; font-size: 0.92rem; }
/* ---- Badges ---- */
.badge-pos { background:#065f46; color:#6ee7b7; padding:2px 10px; border-radius:99px; font-size:0.78rem; }
.badge-neu { background:#3b3a1e; color:#fde68a; padding:2px 10px; border-radius:99px; font-size:0.78rem; }
.badge-neg { background:#7f1d1d; color:#fca5a5; padding:2px 10px; border-radius:99px; font-size:0.78rem; }
/* ---- Headings ---- */
h1, h2, h3 { color: #f9fafb !important; }
/* ---- Buttons ---- */
.stButton > button {
    background: #00D4C8 !important;
    color: #111827 !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    border: none !important;
}
.stButton > button:hover { background: #00b8ae !important; }
/* ---- Dataframe ---- */
.stDataFrame { border-radius: 8px; overflow: hidden; }
/* ---- Tabs ---- */
.stTabs [data-baseweb="tab-list"] { background: #1f2937; border-radius: 8px; }
.stTabs [data-baseweb="tab"] { color: #9ca3af !important; }
.stTabs [aria-selected="true"] { color: #00D4C8 !important; border-bottom-color: #00D4C8 !important; }
/* ---- Login screen ---- */
.login-wrapper {
    display: flex; align-items: center; justify-content: center;
    min-height: 72vh;
}
.login-card {
    background: #1f2937;
    border: 1px solid #374151;
    border-radius: 16px;
    padding: 48px 56px;
    max-width: 420px;
    width: 100%;
    text-align: center;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}
/* Disable pointer events on the password input placeholder row when not authed */
</style>
""", unsafe_allow_html=True)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_report_data(report: dict | None) -> dict:
    """Parse raw_json from a DB row into a Python dict."""
    if not report:
        return {}
    try:
        return json.loads(report["raw_json"])
    except Exception:
        return {}


def sentiment_badge(sentiment: str) -> str:
    s = sentiment.lower()
    if "pos" in s:
        return '<span class="badge-pos">🟢 Positive</span>'
    if "neg" in s:
        return '<span class="badge-neg">🔴 Negative</span>'
    return '<span class="badge-neu">🟠 Neutral</span>'


def run_surveillance_thread(use_batch: bool):
    """Runs the surveillance in a background thread so Streamlit doesn't block.

    The surveillance_running flag is held True for the entire duration and
    always released in the finally block — even on exception — so the button
    can never get permanently stuck in a disabled state.
    """
    from agent import run_surveillance
    try:
        run_surveillance(use_batch=use_batch)
        st.session_state["run_status"] = "done"
    except Exception as exc:
        st.session_state["run_status"] = f"error: {exc}"
    finally:
        st.session_state["surveillance_running"] = False
        st.session_state["job_start_time"] = None


# (Session state and password gate have already run at the top of the file.)


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💊 Opdivo Surveillance")
    st.markdown("---")

    page = st.radio(
        "Navigation",
        [
            "📊 Dashboard",
            "🔬 Pipeline Tracker",
            "✅ Verified Intelligence",
            "📣 Social Noise",
            "🤖 AI Insights",
            "📅 Timeline",
            "🌍 LR Markets",
            "🕑 History",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("### ⚡ Run Surveillance")

    # Single read of the flag — avoids repeated dict lookups and keeps logic clear
    job_running: bool = bool(st.session_state["surveillance_running"])

    run_mode = st.selectbox(
        "Mode",
        ["Batch (50% cheaper)", "Sync (faster)"],
        disabled=job_running,          # locked while job is in flight
        key="run_mode_select",
    )
    use_batch = "Batch" in run_mode

    # ── Run Now button ─────────────────────────────────────────────────────
    btn_label = "⏳ Job Running…" if job_running else "▶ Run Now"
    clicked = st.button(
        btn_label,
        disabled=job_running,          # visually disabled + unclickable
        use_container_width=True,
        type="primary" if not job_running else "secondary",
    )

    if clicked:
        # Double-click / race-condition guard: re-check the flag atomically
        if st.session_state["surveillance_running"]:
            st.warning("⚠️ A job is already running — please wait for it to finish.")
        else:
            # Acquire the lock before spawning the thread
            st.session_state["surveillance_running"] = True
            st.session_state["run_status"] = "running"
            st.session_state["job_start_time"] = datetime.now()
            t = threading.Thread(
                target=run_surveillance_thread,
                args=(use_batch,),
                daemon=True,
            )
            t.start()
            st.rerun()   # immediately re-render so the button disables right away

    # ── In-progress indicator ──────────────────────────────────────────────
    # (sleep + rerun is handled by the full-page banner in the main content area)
    run_status = st.session_state["run_status"]

    if job_running:
        # Compact sidebar chip — the main content area shows the full banner
        start: datetime | None = st.session_state.get("job_start_time")
        if start:
            elapsed_sec = int((datetime.now() - start).total_seconds())
            elapsed_min = elapsed_sec // 60
            elapsed_str = (
                f"{elapsed_min}m {elapsed_sec % 60:02d}s"
                if elapsed_min else f"{elapsed_sec}s"
            )
        else:
            elapsed_str = "…"
        st.markdown(
            f'<div style="background:#14532d;border:1px solid #166534;border-radius:8px;'
            f'padding:10px 12px;font-size:0.82rem;color:#bbf7d0;line-height:1.6;">'
            f'<b style="color:#4ade80;">⚙️ Job running</b><br>'
            f'🕐 {elapsed_str} elapsed<br>'
            f'<span style="color:#86efac;">See main area for details.</span></div>',
            unsafe_allow_html=True,
        )

    elif run_status == "done":
        # Job finished — pull the fresh report from DB, cache it, then rerun
        # once so the dashboard immediately shows the new data.
        st.session_state["last_report"] = get_latest_report()
        st.session_state["run_status"] = ""
        st.rerun()
    elif run_status.startswith("error"):
        st.error(f"❌ {run_status}")
        st.session_state["run_status"] = ""

    st.markdown("---")
    _cached = st.session_state["last_report"]
    if _cached:
        _ts = _cached.get("run_date", "")[:19].replace("T", " ")
        # Show report age
        try:
            _age = datetime.now() - datetime.fromisoformat(_cached.get("run_date", ""))
            _age_h = int(_age.total_seconds() // 3600)
            _age_d = _age.days
            _age_str = (
                f"{_age_d}d ago" if _age_d >= 1
                else f"{_age_h}h ago" if _age_h >= 1
                else "< 1h ago"
            )
        except Exception:
            _age_str = ""
        st.markdown(
            f'<div style="background:#1f2937;border:1px solid #374151;border-radius:8px;'
            f'padding:10px 12px;font-size:0.80rem;color:#9ca3af;line-height:1.6;">'
            f'<b style="color:#d1d5db;">📄 Cached Report</b><br>'
            f'{_ts}<br>'
            f'<span style="color:#6b7280;">{_age_str}</span></div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("No report yet. Click ▶ Run Now.")

    st.markdown("---")
    if st.button("🔒 Log Out", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()


# ─── Load data from session-state cache ──────────────────────────────────────
# Always read from the cached report so we avoid redundant DB queries on every
# 30-second rerun while a job is polling.  The cache is invalidated (refreshed
# from DB) in two places:
#   1. Immediately after a job completes (run_status == "done" handler above).
#   2. On the very first load of the session (initialised in session-state boot).
latest = st.session_state["last_report"]
data = load_report_data(latest)

companies       = data.get("companies", [])
verified        = data.get("verified_updates", [])
social          = data.get("social_noise", [])
ai_insights     = data.get("ai_insights", "")
exec_summary    = data.get("executive_summary", "")

# ─── Full-page progress banner (shown on every page while job is in flight) ───
if st.session_state["surveillance_running"]:
    _start: datetime | None = st.session_state.get("job_start_time")
    if _start:
        _elapsed_s   = int((datetime.now() - _start).total_seconds())
        _elapsed_min = _elapsed_s // 60
        _elapsed_str = (
            f"{_elapsed_min}m {_elapsed_s % 60:02d}s"
            if _elapsed_min else f"{_elapsed_s}s"
        )
    else:
        _elapsed_str = "just started"

    _use_batch = "Batch" in st.session_state.get("run_mode_select", "Batch")
    _eta = "30 minutes to a few hours" if _use_batch else "1 – 5 minutes"
    _mode_label = "Grok Batch API (50% cheaper)" if _use_batch else "Synchronous API"
    _close_note = (
        "You can safely close this tab — the job runs in the background."
        if _use_batch
        else "Keep this tab open until the job finishes."
    )

    st.markdown(
        f"""
<div style="
  background: linear-gradient(135deg,#0f2027,#1a3a2a);
  border: 2px solid #16a34a;
  border-radius: 16px;
  padding: 36px 40px;
  margin-bottom: 28px;
  box-shadow: 0 4px 32px rgba(0,212,150,0.15);
">
  <div style="display:flex;align-items:center;gap:16px;margin-bottom:20px;">
    <div style="font-size:2.4rem;line-height:1;">⚙️</div>
    <div>
      <div style="color:#4ade80;font-size:1.35rem;font-weight:800;letter-spacing:-0.01em;">
        Surveillance job is running in the background…
      </div>
      <div style="color:#86efac;font-size:0.88rem;margin-top:3px;">
        Mode: <b>{_mode_label}</b>
      </div>
    </div>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:24px;">
    <div style="background:#14532d44;border:1px solid #166534;border-radius:10px;padding:14px 18px;">
      <div style="color:#86efac;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:4px;">⏱ Elapsed</div>
      <div style="color:#f0fdf4;font-size:1.4rem;font-weight:700;">{_elapsed_str}</div>
    </div>
    <div style="background:#14532d44;border:1px solid #166534;border-radius:10px;padding:14px 18px;">
      <div style="color:#86efac;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:4px;">⏳ Estimated Duration</div>
      <div style="color:#f0fdf4;font-size:1rem;font-weight:600;">{_eta}</div>
    </div>
    <div style="background:#14532d44;border:1px solid #166534;border-radius:10px;padding:14px 18px;">
      <div style="color:#86efac;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:4px;">📡 Status</div>
      <div style="color:#4ade80;font-size:1rem;font-weight:600;">Active — polling Grok</div>
    </div>
  </div>

  <div style="background:#052e16;border:1px solid #166534;border-radius:8px;padding:12px 16px;
              color:#bbf7d0;font-size:0.88rem;line-height:1.7;">
    💡 <b>{_close_note}</b><br>
    🔄 This page auto-refreshes every 30 seconds. New results will appear automatically when ready.<br>
    🚫 The <b>Run Now</b> button is locked until this job completes.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    # Animated Streamlit progress bar — cycles to show activity
    import time as _time
    _progress_pct = min(95, (_elapsed_s // 60) * 3) if _start else 10  # caps at 95%
    _prog_bar = st.progress(_progress_pct / 100, text=f"Grok is processing your request… ({_elapsed_str} elapsed)")

    # 30-second sleep then rerun (keeps session alive, no browser reload)
    _time.sleep(30)
    st.rerun()

# ─── Page routing ─────────────────────────────────────────────────────────────

# ══════════════════════════════════════════════════════════════════════════════
# 1. DASHBOARD OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
if page == "📊 Dashboard":
    st.title("📊 Dashboard Overview")
    st.caption("Opdivo (nivolumab) biosimilar competitive intelligence — powered by Grok AI")

    if not data:
        st.warning("No report found. Use the sidebar to run a new surveillance sweep.")
        st.stop()

    # ── Cached-report info strip ────────────────────────────────────────────
    if latest:
        try:
            _rpt_age = datetime.now() - datetime.fromisoformat(latest.get("run_date", ""))
            _rpt_h   = int(_rpt_age.total_seconds() // 3600)
            _rpt_d   = _rpt_age.days
            _rpt_age_str = (
                f"{_rpt_d} day{'s' if _rpt_d != 1 else ''} ago"
                if _rpt_d >= 1 else
                f"{_rpt_h} hour{'s' if _rpt_h != 1 else ''} ago"
                if _rpt_h >= 1 else "less than 1 hour ago"
            )
            _rpt_ts = latest.get("run_date", "")[:19].replace("T", " ")
            st.markdown(
                f'<div style="background:#1f2937;border:1px solid #374151;border-radius:8px;'
                f'padding:9px 16px;margin-bottom:16px;font-size:0.82rem;color:#9ca3af;'
                f'display:flex;align-items:center;gap:10px;">'
                f'<span style="color:#00D4C8;font-size:1rem;">📋</span>'
                f'Showing <b style="color:#d1d5db;">cached report</b> from '
                f'<b style="color:#d1d5db;">{_rpt_ts}</b> &nbsp;·&nbsp; {_rpt_age_str}'
                f'&nbsp;&nbsp;<span style="color:#4b5563;">|&nbsp; Run a new sweep to refresh.</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        except Exception:
            pass

    # ── Derived KPI values ──────────────────────────────────────────────────
    launched_cos  = [c for c in companies if "launch" in c.get("phase", "").lower()]
    launched_count = len(launched_cos)
    avg_prob   = (sum(c.get("probability", 0) for c in companies) / len(companies)) if companies else 0
    new_alerts = len([v for v in verified if v.get("date", "") >= datetime.now().strftime("%Y-%m")])

    # ── KPI row (5 columns) ──────────────────────────────────────────────────
    my_threats = data.get("my_markets_threat", []) if data else []
    threat_count = len({t.get("company", "") for t in my_threats if t.get("company")})

    kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)

    # Hardcoded baseline list shown even when Grok returns no data
    _BASELINE_COMPANIES = [
        "Zydus Lifesciences", "Amgen (ABP 206)", "Sandoz", "Boan Biotech",
        "Henlius (HLX18)", "Reliance Life Sciences", "Xbrane / Intas",
        "Biocon", "Samsung Bioepis", "Innovent", "Celltrion",
    ]
    # Merge: dynamic companies first, then append any baseline names not already present
    grok_names = {c.get("company", "").lower() for c in companies}
    extra_baseline = [
        n for n in _BASELINE_COMPANIES
        if not any(n.lower().split()[0] in gn for gn in grok_names)
    ]
    display_count = len(companies) if companies else len(_BASELINE_COMPANIES)

    # --- Card 1: Companies Monitored (with popover listing all companies) ----
    with kpi1:
        st.markdown(
            f'<div class="kpi-card"><div class="kpi-value">{display_count}</div>'
            f'<div class="kpi-label">Companies Monitored</div></div>',
            unsafe_allow_html=True,
        )
        with st.expander("👁 View all companies", expanded=False):
            # Dynamic entries from Grok (with phase badges)
            for c in companies:
                phase   = c.get("phase", "")
                is_live = "launch" in phase.lower()
                badge   = ' <span style="background:#065f46;color:#6ee7b7;padding:1px 7px;border-radius:99px;font-size:0.72rem;font-weight:600;">✅ Launched</span>' if is_live else ""
                st.markdown(
                    f"**{c.get('company','')}** — {c.get('biosimilar','')} "
                    f"<span style='color:#9ca3af;font-size:0.82rem;'>({phase})</span>{badge}",
                    unsafe_allow_html=True,
                )
            # Baseline companies not returned by Grok this run
            if extra_baseline:
                if companies:
                    st.markdown("<hr style='border-color:#374151;margin:8px 0;'>", unsafe_allow_html=True)
                    st.caption("Also tracked (no update this run):")
                for name in extra_baseline:
                    st.markdown(f"◦ {name}", unsafe_allow_html=False)

    # --- Card 2: New Alerts ---------------------------------------------------
    with kpi2:
        st.markdown(
            f'<div class="kpi-card"><div class="kpi-value">{new_alerts}</div>'
            f'<div class="kpi-label">New Alerts This Month</div></div>',
            unsafe_allow_html=True,
        )

    # --- Card 3: Launched count (with names) ---------------------------------
    with kpi3:
        launched_label = "Biosimilar Launched" if launched_count == 1 else "Biosimilars Launched"
        st.markdown(
            f'<div class="kpi-card" style="border-color:#10b981;">'
            f'<div class="kpi-value" style="color:#10b981;">{launched_count}</div>'
            f'<div class="kpi-label">{launched_label}</div></div>',
            unsafe_allow_html=True,
        )
        if launched_cos:
            with st.expander("✅ View launched", expanded=False):
                for c in launched_cos:
                    st.markdown(
                        f"🟢 **{c.get('company','')}** · {c.get('biosimilar','')}  \n"
                        f"<span style='color:#9ca3af;font-size:0.82rem;'>Markets: {c.get('countries','—')}</span>",
                        unsafe_allow_html=True,
                    )
        else:
            st.caption(
                "ℹ️ No launched biosimilars in this report. "
                "**Zydus Tishtha** is known to be launched in India (2026). "
                "Re-run surveillance to get the latest data."
            )

    # --- Card 4: My Markets Threats -----------------------------------------
    with kpi4:
        threat_color = "#ef4444" if threat_count > 0 else "#6b7280"
        _hi_t = [t for t in my_threats if t.get("risk_level") == "High"]
        _top_country = _hi_t[0].get("country", "") if _hi_t else (
            my_threats[0].get("country", "") if my_threats else ""
        )
        _sub = f"⚠️ Watch: {_top_country}" if _top_country else "No active threats"
        st.markdown(
            f'<div class="kpi-card" style="border-color:{threat_color};">'
            f'<div class="kpi-value" style="color:{threat_color};">{threat_count}</div>'
            f'<div class="kpi-label">Threats in My Markets</div>'
            f'<div style="color:#9ca3af;font-size:0.70rem;margin-top:4px;">{_sub}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if my_threats:
            with st.expander("📋 By model", expanded=False):
                _OM_KPI_COLORS = {
                    "LPM":     ("#7f1d1d", "#fca5a5"),
                    "OPM":     ("#78350f", "#fde68a"),
                    "Passive": ("#1f2937", "#9ca3af"),
                }
                for _om in ("LPM", "OPM", "Passive"):
                    _cnt = sum(1 for t in my_threats if t.get("operational_model") == _om)
                    if _cnt:
                        _bg, _fg = _OM_KPI_COLORS[_om]
                        st.markdown(
                            f'<span style="background:{_bg};color:{_fg};padding:1px 7px;'
                            f'border-radius:99px;font-size:0.72rem;font-weight:700;">{_om}</span>'
                            f' {_cnt} threat{"s" if _cnt != 1 else ""}',
                            unsafe_allow_html=True,
                        )

    # --- Card 5: Avg Probability ---------------------------------------------
    with kpi5:
        st.markdown(
            f'<div class="kpi-card"><div class="kpi-value">{avg_prob:.0f}%</div>'
            f'<div class="kpi-label">Avg Launch Probability</div></div>',
            unsafe_allow_html=True,
        )

    # --- Card 6: Highest-risk competitor -------------------------------------
    with kpi6:
        if companies:
            top = max(companies, key=lambda c: c.get("probability", 0))
            top_name = top.get("company", "—").split()[0]   # first word to keep it short
            st.markdown(
                f'<div class="kpi-card" style="border-color:#f59e0b;">'
                f'<div class="kpi-value" style="color:#f59e0b;font-size:1.3rem;">{top_name}</div>'
                f'<div class="kpi-label">Highest Risk Competitor</div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="kpi-card"><div class="kpi-value">—</div>'
                '<div class="kpi-label">Highest Risk Competitor</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # Executive summary
    st.subheader("🔑 Executive Summary")
    st.info(exec_summary or "No summary available.")

    st.markdown("---")

    # Latest verified updates (first 4)
    st.subheader("📋 Latest Verified Updates")
    for item in verified[:4]:
        st.markdown(
            f'<div class="update-card">'
            f'<div class="source">📌 {item.get("source","")} &nbsp;·&nbsp; {item.get("date","")}</div>'
            f'<div class="title">{item.get("title","")}</div>'
            f'<div class="body">{item.get("summary","")}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if not verified:
        st.info("No verified updates in this report.")


# ══════════════════════════════════════════════════════════════════════════════
# 2. PIPELINE TRACKER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔬 Pipeline Tracker":
    st.title("🔬 Pipeline Tracker")

    if not companies:
        st.warning("No pipeline data. Run a surveillance sweep first.")
        st.stop()

    df = pd.DataFrame(companies)

    # ── Quick-filter: Launched only toggle ───────────────────────────────────
    launched_only = st.toggle("✅ Show Launched only", value=False)

    # ── Filters row ──────────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 3])
    company_filter = fc1.multiselect("Company",  sorted(df["company"].unique()))
    phase_filter   = fc2.multiselect("Phase",    sorted(df["phase"].unique()))
    country_filter = fc3.text_input("Country contains")
    search_filter  = fc4.text_input("🔍 Search")

    fdf = df.copy()
    if launched_only:
        fdf = fdf[fdf["phase"].str.contains("launch", case=False, na=False)]
    if company_filter:
        fdf = fdf[fdf["company"].isin(company_filter)]
    if phase_filter:
        fdf = fdf[fdf["phase"].isin(phase_filter)]
    if country_filter:
        fdf = fdf[fdf["countries"].str.contains(country_filter, case=False, na=False)]
    if search_filter:
        mask = fdf.apply(lambda row: row.astype(str).str.contains(search_filter, case=False).any(), axis=1)
        fdf = fdf[mask]

    ecol, _ = st.columns([1, 5])
    if ecol.button("⬇ Export CSV"):
        st.download_button(
            "Download CSV",
            data=fdf.to_csv(index=False).encode(),
            file_name="opdivo_pipeline.csv",
            mime="text/csv",
        )

    # ── Render table as HTML to allow per-row badge styling ──────────────────
    def _phase_cell(phase: str) -> str:
        if "launch" in phase.lower():
            return (
                f'<span style="background:#065f46;color:#6ee7b7;padding:3px 10px;'
                f'border-radius:99px;font-size:0.82rem;font-weight:700;">✅ Launched</span>'
            )
        if "approved" in phase.lower():
            return (
                f'<span style="background:#1e3a5f;color:#93c5fd;padding:3px 10px;'
                f'border-radius:99px;font-size:0.82rem;font-weight:600;">{phase}</span>'
            )
        if "bla" in phase.lower() or "submit" in phase.lower():
            return (
                f'<span style="background:#3b2500;color:#fbbf24;padding:3px 10px;'
                f'border-radius:99px;font-size:0.82rem;font-weight:600;">{phase}</span>'
            )
        return f'<span style="color:#d1d5db;">{phase}</span>'

    def _prob_cell(prob: int) -> str:
        color = "#10b981" if prob >= 70 else ("#f59e0b" if prob >= 40 else "#ef4444")
        bar_w = max(4, prob)
        return (
            f'<div style="display:flex;align-items:center;gap:8px;">'
            f'<div style="background:#374151;border-radius:4px;width:80px;height:8px;">'
            f'<div style="background:{color};border-radius:4px;width:{bar_w}%;height:8px;"></div></div>'
            f'<span style="color:{color};font-weight:600;">{prob}%</span></div>'
        )

    html_rows = ""
    for _, row in fdf.iterrows():
        is_launched = "launch" in str(row.get("phase", "")).lower()
        row_bg = "background:#052e16;" if is_launched else ""
        html_rows += (
            f'<tr style="{row_bg}">'
            f'<td style="padding:10px 12px;font-weight:600;">{row.get("company","")}</td>'
            f'<td style="padding:10px 12px;color:#a5b4fc;">{row.get("biosimilar","")}</td>'
            f'<td style="padding:10px 12px;">{_phase_cell(str(row.get("phase","")))}</td>'
            f'<td style="padding:10px 12px;color:#d1d5db;font-size:0.88rem;">{row.get("status","")}</td>'
            f'<td style="padding:10px 12px;color:#9ca3af;">{row.get("countries","")}</td>'
            f'<td style="padding:10px 12px;">{row.get("est_launch","")}</td>'
            f'<td style="padding:10px 12px;">{_prob_cell(int(row.get("probability", 0)))}</td>'
            f'<td style="padding:10px 12px;color:#9ca3af;font-size:0.85rem;">{row.get("strengths_weaknesses","")}</td>'
            f'</tr>'
        )

    html_table = f"""
    <div style="overflow-x:auto;border-radius:10px;border:1px solid #374151;">
    <table style="width:100%;border-collapse:collapse;background:#1f2937;color:#f3f4f6;font-size:0.9rem;">
      <thead>
        <tr style="background:#111827;border-bottom:2px solid #374151;">
          <th style="padding:12px;text-align:left;color:#9ca3af;">Company</th>
          <th style="padding:12px;text-align:left;color:#9ca3af;">Biosimilar</th>
          <th style="padding:12px;text-align:left;color:#9ca3af;">Phase</th>
          <th style="padding:12px;text-align:left;color:#9ca3af;">Status</th>
          <th style="padding:12px;text-align:left;color:#9ca3af;">Countries</th>
          <th style="padding:12px;text-align:left;color:#9ca3af;">Est. Launch</th>
          <th style="padding:12px;text-align:left;color:#9ca3af;">Probability</th>
          <th style="padding:12px;text-align:left;color:#9ca3af;">Notes</th>
        </tr>
      </thead>
      <tbody>
        {html_rows}
      </tbody>
    </table>
    </div>
    """
    st.markdown(html_table, unsafe_allow_html=True)

    # Probability bar chart
    st.markdown("---")
    st.subheader("Launch Probability by Company")
    fig = px.bar(
        fdf.sort_values("probability", ascending=True),
        x="probability",
        y="company",
        orientation="h",
        color="probability",
        color_continuous_scale=[[0, "#ef4444"], [0.5, "#f59e0b"], [1, "#10b981"]],
        labels={"probability": "Probability (%)", "company": ""},
        template="plotly_dark",
    )
    fig.update_layout(
        paper_bgcolor="#111827",
        plot_bgcolor="#1f2937",
        coloraxis_showscale=False,
        height=max(300, len(fdf) * 36),
    )
    st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# 3. VERIFIED INTELLIGENCE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "✅ Verified Intelligence":
    st.title("✅ Verified Intelligence")

    if not verified:
        st.warning("No verified updates. Run a surveillance sweep first.")
        st.stop()

    source_filter = st.multiselect(
        "Filter by source",
        sorted({v.get("source", "Unknown") for v in verified}),
    )

    filtered = [v for v in verified if (not source_filter or v.get("source") in source_filter)]

    for item in filtered:
        with st.expander(f"📌 {item.get('title', 'Untitled')}  —  {item.get('date', '')}"):
            st.markdown(f"**Source**: {item.get('source', 'Unknown')}")
            st.markdown(item.get("summary", "No details available."))


# ══════════════════════════════════════════════════════════════════════════════
# 4. SOCIAL NOISE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📣 Social Noise":
    st.title("📣 Social Noise")

    if not social:
        st.warning("No social data. Run a surveillance sweep first.")
        st.stop()

    left, right = st.columns([7, 3])

    with left:
        sent_filter = st.multiselect("Filter by sentiment", ["Positive", "Neutral", "Negative"])
        posts = [p for p in social if (not sent_filter or p.get("sentiment") in sent_filter)]
        for post in posts:
            st.markdown(
                f'<div class="post-card">'
                f'<span class="user">{post.get("user","@unknown")}</span>'
                f'<span class="time">{post.get("time","")}</span> '
                f'{sentiment_badge(post.get("sentiment","Neutral"))}'
                f'<div class="text">{post.get("post","")}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    with right:
        st.subheader("Sentiment")
        counts = {"Positive": 0, "Neutral": 0, "Negative": 0}
        for p in social:
            s = p.get("sentiment", "Neutral")
            if s in counts:
                counts[s] += 1
            else:
                counts["Neutral"] += 1
        pie = go.Figure(go.Pie(
            labels=list(counts.keys()),
            values=list(counts.values()),
            marker_colors=["#10b981", "#f59e0b", "#ef4444"],
            hole=0.45,
        ))
        pie.update_layout(
            paper_bgcolor="#111827",
            font_color="#f3f4f6",
            showlegend=True,
            height=280,
            margin=dict(t=20, b=20, l=20, r=20),
        )
        st.plotly_chart(pie, use_container_width=True)

        st.subheader("Top Keywords")
        from collections import Counter
        import re
        stop = {"a","an","the","and","or","of","to","in","is","it","for","on","at","by","with","as","be","are","was","were","has","have"}
        words = []
        for p in social:
            words += [w.lower() for w in re.findall(r"[a-zA-Z]{4,}", p.get("post","")) if w.lower() not in stop]
        top_words = Counter(words).most_common(10)
        if top_words:
            wdf = pd.DataFrame(top_words, columns=["Word", "Count"])
            st.bar_chart(wdf.set_index("Word"))


# ══════════════════════════════════════════════════════════════════════════════
# 5. AI INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🤖 AI Insights":
    st.title("🤖 AI Insights")

    if not data:
        st.warning("No data. Run a surveillance sweep first.")
        st.stop()

    st.subheader("Executive Summary")
    st.info(exec_summary or "—")

    st.markdown("---")
    st.subheader("Grok's Deep Reasoning")
    st.markdown(ai_insights or "No AI insights available in this report.", unsafe_allow_html=False)

    st.markdown("---")
    st.subheader("Competitive Risk Heatmap")

    if companies:
        heat_df = pd.DataFrame({
            "Company": [c["company"] for c in companies],
            "Launch Probability (%)": [c.get("probability", 0) for c in companies],
        }).set_index("Company")

        fig_heat = px.imshow(
            heat_df.T,
            color_continuous_scale=[[0, "#7f1d1d"], [0.5, "#78350f"], [1, "#065f46"]],
            aspect="auto",
            template="plotly_dark",
            labels={"color": "Probability (%)"},
        )
        fig_heat.update_layout(
            paper_bgcolor="#111827",
            plot_bgcolor="#1f2937",
            height=160,
        )
        st.plotly_chart(fig_heat, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# 6. TIMELINE (Gantt-style)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📅 Timeline":
    st.title("📅 Competitive Timeline")

    if not companies:
        st.warning("No pipeline data. Run a surveillance sweep first.")
        st.stop()

    PHASE_ORDER = [
        "Pre-clinical", "Phase I", "Phase II", "Phase III",
        "BLA Submitted", "Approved", "Launched",
    ]
    PHASE_COLORS = {
        "Pre-clinical":  "#6b7280",
        "Phase I":       "#3B82F6",
        "Phase II":      "#8b5cf6",
        "Phase III":     "#f59e0b",
        "BLA Submitted": "#f97316",
        "Approved":      "#10b981",
        "Launched":      "#00D4C8",
        "Rejected":      "#ef4444",
    }

    def phase_to_months(phase: str) -> tuple[int, int]:
        """Return (start_offset_months, duration_months) from today."""
        idx = PHASE_ORDER.index(phase) if phase in PHASE_ORDER else 0
        start = idx * 4
        return start, 6

    today = datetime.now()
    gantt_rows = []
    for c in companies:
        phase = c.get("phase", "Pre-clinical")
        start_off, dur = phase_to_months(phase)
        start_dt = pd.Timestamp(today.year, today.month, 1) + pd.DateOffset(months=start_off)
        end_dt   = start_dt + pd.DateOffset(months=dur)
        gantt_rows.append({
            "Company":   c["company"],
            "Biosimilar": c.get("biosimilar", ""),
            "Phase":     phase,
            "Start":     start_dt,
            "Finish":    end_dt,
            "Probability": c.get("probability", 0),
        })

    gdf = pd.DataFrame(gantt_rows)
    fig_gantt = px.timeline(
        gdf,
        x_start="Start",
        x_end="Finish",
        y="Company",
        color="Phase",
        color_discrete_map=PHASE_COLORS,
        hover_data=["Biosimilar", "Probability"],
        template="plotly_dark",
        title="Estimated Phase Timeline (next 24 months)",
    )
    fig_gantt.update_yaxes(autorange="reversed")
    fig_gantt.update_layout(
        paper_bgcolor="#111827",
        plot_bgcolor="#1f2937",
        font_color="#f3f4f6",
        height=max(400, len(companies) * 44),
        legend_title_text="Phase",
    )
    st.plotly_chart(fig_gantt, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# 7. MY MARKETS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🌍 LR Markets":
    import re as _re
    from datetime import date as _date

    st.title("🌍 LR Markets — Biosimilar Threat Monitor")
    st.caption(
        "Tracks nivolumab biosimilar competitive threats across LR priority markets "
        "(CEE/EU · LATAM · MEA). Built to help Operations teams prepare well in advance."
    )

    # ── Market definitions ──────────────────────────────────────────────────
    _MY_MARKETS: dict = {
        "CEE / EU": {
            "LPM": ["Israel", "Kazakhstan", "Malta", "Russia"],
            "OPM": [
                "Albania", "Bosnia", "Bulgaria", "Croatia", "Estonia", "Kosovo",
                "Latvia", "Lithuania", "Macedonia", "Montenegro", "Serbia",
                "Slovakia", "Slovenia",
            ],
        },
        "LATAM": {
            "LPM": [
                "Bolivia", "Brazil", "Costa Rica", "Dominican Republic", "Ecuador",
                "El Salvador", "Guatemala", "Honduras", "Nicaragua", "Panama",
                "Paraguay", "Uruguay",
            ],
            "Passive": ["Venezuela"],
        },
        "MEA": {
            "LPM": ["Algeria", "Egypt", "Iraq", "Lebanon", "Libya", "Morocco"],
            "Passive": ["South Africa"],
        },
    }

    _OM_STYLE: dict = {
        "LPM":     {"bg": "#7f1d1d", "fg": "#fca5a5", "border": "#ef4444",
                    "desc": "Lead Priority Market — highest commercial focus"},
        "OPM":     {"bg": "#78350f", "fg": "#fde68a", "border": "#f59e0b",
                    "desc": "Operational Priority Market — active but secondary"},
        "Passive": {"bg": "#1e293b", "fg": "#94a3b8", "border": "#475569",
                    "desc": "Passive Market — monitored, limited active investment"},
    }
    _RISK_STYLE: dict = {
        "High":   {"bg": "#7f1d1d", "fg": "#fca5a5", "emoji": "🔴"},
        "Medium": {"bg": "#78350f", "fg": "#fde68a", "emoji": "🟠"},
        "Low":    {"bg": "#1e3a2f", "fg": "#6ee7b7", "emoji": "🟢"},
    }

    # ── Helper: time to threat ───────────────────────────────────────────────
    def _ttt(est_launch: str, phase: str) -> str:
        if "launch" in phase.lower():
            return "⚡ Already on market"
        if not est_launch or est_launch.strip().upper() == "TBD":
            return "Timeline unknown"
        today = _date(2026, 4, 1)
        el = est_launch.strip()
        qm = _re.match(r"Q([1-4])\s*/?\s*(\d{4})", el)
        if qm:
            q, yr = int(qm.group(1)), int(qm.group(2))
            mid = {1: 2, 2: 5, 3: 8, 4: 11}[q]
            target = _date(yr, mid, 1)
            months = (target.year - today.year) * 12 + (target.month - today.month)
            return "⚡ Imminent / Overdue" if months <= 0 else f"~{months} months"
        ym = _re.match(r"(\d{4})$", el)
        if ym:
            yr = int(ym.group(1))
            lo = (yr - today.year) * 12 - today.month + 1
            hi = lo + 11
            if hi <= 0:
                return "⚡ Imminent / Overdue"
            return f"Within {hi} months" if lo <= 0 else f"{lo}–{hi} months"
        return el

    # ── Helper: recommended actions ──────────────────────────────────────────
    def _actions(phase: str, risk: str) -> list:
        pl = phase.lower()
        if "launch" in pl:
            acts = [
                "Activate tender defense strategy immediately",
                "Engage KOLs to reinforce Opdivo clinical value",
                "Prepare price-erosion budget analysis",
            ]
        elif "approved" in pl:
            acts = [
                "Launch tender defense playbook now",
                "Accelerate local registration to stay competitive",
                "Brief payers on Opdivo differentiators",
            ]
        elif any(x in pl for x in ("submitted", "bla", "filing", "nda")):
            acts = [
                "Prepare tender strategy — approval likely within 12 months",
                "Initiate local market access planning",
                "Engage KOLs and payers early",
            ]
        elif any(x in pl for x in ("phase iii", "phase 3")):
            acts = [
                "Monitor regulatory filing timeline closely",
                "Build Opdivo preference with KOLs now",
                "Develop payer value messaging",
            ]
        elif any(x in pl for x in ("phase ii", "phase 2")):
            acts = [
                "Track trial progression and interim data",
                "Begin competitive dossier preparation",
            ]
        else:
            acts = [
                "Maintain awareness — no immediate action required",
                "Monitor for trial or regulatory filing activity",
            ]
        if risk == "High":
            acts.insert(0, "⚡ Escalate to regional leadership")
        return acts[:3]

    # ── Build/fallback threat list ───────────────────────────────────────────
    raw_threats: list = (data or {}).get("my_markets_threat", [])

    if not raw_threats and companies:
        _all_lr: dict = {}
        for _rgn, _models in _MY_MARKETS.items():
            for _om, _ctries in _models.items():
                for _c in _ctries:
                    _all_lr[_c.lower()] = (_rgn, _om)
        for comp in companies:
            for _cr in comp.get("countries", "").split(","):
                _c = _cr.strip()
                _match = _all_lr.get(_c.lower())
                if _match:
                    _rgn, _om = _match
                    prob = comp.get("probability", 0)
                    raw_threats.append({
                        "country":           _c,
                        "region":            _rgn,
                        "operational_model": _om,
                        "company":           comp.get("company", ""),
                        "biosimilar":        comp.get("biosimilar", ""),
                        "phase":             comp.get("phase", ""),
                        "est_launch":        comp.get("est_launch", "TBD"),
                        "risk_level":        "High" if prob >= 70 else "Medium" if prob >= 40 else "Low",
                    })

    # ── Summary KPI strip ────────────────────────────────────────────────────
    _total  = len(raw_threats)
    _n_high = sum(1 for t in raw_threats if t.get("risk_level") == "High")
    _n_cos  = len({t.get("company", "") for t in raw_threats if t.get("company")})
    _n_ctry = len({t.get("country", "")  for t in raw_threats if t.get("country")})

    sk1, sk2, sk3, sk4 = st.columns(4)
    sk1.metric("Total Active Threats",  _total)
    sk2.metric("High-Risk Threats",     _n_high,
               delta="Needs immediate attention" if _n_high else None)
    sk3.metric("Competitor Companies",  _n_cos)
    sk4.metric("Countries at Risk",     _n_ctry)

    if not raw_threats and not data:
        st.info("No surveillance data available yet. Run a surveillance sweep from the sidebar to populate threat intelligence.")
        st.stop()

    st.markdown("---")

    # ── Cascading view: Region → Ops Model → Country threat cards ────────────
    _threat_idx: dict = {}  # (region, om, country) -> list[threat]
    for t in raw_threats:
        key = (t.get("region", ""), t.get("operational_model", ""), t.get("country", ""))
        _threat_idx.setdefault(key, []).append(t)

    _risk_order = {"High": 0, "Medium": 1, "Low": 2}

    for region, models in _MY_MARKETS.items():
        _rc = sum(1 for t in raw_threats if t.get("region") == region)
        _rhi = sum(1 for t in raw_threats if t.get("region") == region and t.get("risk_level") == "High")
        _r_badge = f"  —  {_rc} threat{'s' if _rc != 1 else ''}" if _rc else "  —  No active threats"
        _hi_tag = f"  🔴 {_rhi} High-risk" if _rhi else ""

        with st.expander(f"🌍 **{region}**{_r_badge}{_hi_tag}", expanded=(_rc > 0)):

            # One section per operational model
            for om, countries in models.items():
                om_style = _OM_STYLE.get(om, {"bg": "#1f2937", "fg": "#9ca3af",
                                               "border": "#374151", "desc": ""})
                om_threats = [t for t in raw_threats
                              if t.get("region") == region and t.get("operational_model") == om]
                om_count = len(om_threats)

                # Model header
                _cnt_span = (
                    f'<span style="margin-left:auto;color:#ef4444;font-weight:700;'
                    f'font-size:0.82rem;">{om_count} threat{"s" if om_count != 1 else ""}</span>'
                    if om_count else ""
                )
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:10px;'
                    f'margin:18px 0 10px 0;padding:8px 14px;'
                    f'background:{om_style["bg"]}22;border-left:3px solid {om_style["border"]};'
                    f'border-radius:0 6px 6px 0;">'
                    f'<span style="background:{om_style["bg"]};color:{om_style["fg"]};'
                    f'padding:2px 10px;border-radius:99px;font-size:0.78rem;font-weight:700;">{om}</span>'
                    f'<span style="color:{om_style["fg"]};font-size:0.80rem;">{om_style["desc"]}</span>'
                    f'{_cnt_span}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                if not om_threats:
                    # Show clean country list — no threats
                    _country_list = " · ".join(countries)
                    st.markdown(
                        f'<p style="color:#6b7280;font-size:0.82rem;margin:0 0 12px 14px;">'
                        f'⚪ No active threats — monitoring: {_country_list}</p>',
                        unsafe_allow_html=True,
                    )
                    continue

                # Group threats by country, sort by risk
                _by_country: dict = {}
                for t in om_threats:
                    _by_country.setdefault(t.get("country", ""), []).append(t)

                # Sort countries: threatened first (by worst risk), then clean
                _threatened = sorted(
                    _by_country.keys(),
                    key=lambda c: min(_risk_order.get(t.get("risk_level", "Low"), 3)
                                      for t in _by_country[c])
                )
                _clean = [c for c in countries if c not in _by_country]

                # Country threat cards (two per row)
                card_chunks = [_threatened[i:i+2] for i in range(0, len(_threatened), 2)]
                for chunk in card_chunks:
                    card_cols = st.columns(len(chunk))
                    for col, country in zip(card_cols, chunk):
                        threats_for_country = sorted(
                            _by_country[country],
                            key=lambda t: _risk_order.get(t.get("risk_level", "Low"), 3)
                        )
                        worst_risk = threats_for_country[0].get("risk_level", "Low")
                        rs = _RISK_STYLE.get(worst_risk, _RISK_STYLE["Low"])

                        with col:
                            # Card header
                            st.markdown(
                                f'<div style="background:#1f2937;border:1px solid {rs["bg"]};'
                                f'border-top:3px solid {rs["bg"]};border-radius:8px;'
                                f'padding:12px 14px;margin-bottom:10px;">'
                                f'<div style="display:flex;justify-content:space-between;'
                                f'align-items:center;margin-bottom:8px;">'
                                f'<span style="font-weight:700;font-size:0.95rem;'
                                f'color:#f3f4f6;">📍 {country}</span>'
                                f'<span style="background:{rs["bg"]};color:{rs["fg"]};'
                                f'padding:2px 9px;border-radius:99px;font-size:0.72rem;'
                                f'font-weight:700;">{rs["emoji"]} {worst_risk}</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                            for t in threats_for_country:
                                phase = t.get("phase", "")
                                est   = t.get("est_launch", "TBD")
                                ttt   = _ttt(est, phase)
                                acts  = _actions(phase, t.get("risk_level", "Low"))
                                ttt_color = (
                                    "#ef4444" if "Imminent" in ttt or "Already" in ttt
                                    else "#f59e0b" if "months" in ttt
                                    else "#9ca3af"
                                )
                                acts_html = "".join(
                                    f'<li style="margin:2px 0;">{a}</li>' for a in acts
                                )
                                st.markdown(
                                    f'<div style="border-top:1px solid #374151;'
                                    f'padding-top:8px;margin-top:6px;">'
                                    f'<div style="font-weight:600;color:#e2e8f0;'
                                    f'font-size:0.85rem;">{t.get("company","")}</div>'
                                    f'<div style="color:#94a3b8;font-size:0.78rem;'
                                    f'margin-bottom:4px;">{t.get("biosimilar","")} &nbsp;·&nbsp; {phase}</div>'
                                    f'<div style="color:{ttt_color};font-size:0.78rem;'
                                    f'font-weight:600;margin-bottom:6px;">⏱ {ttt}</div>'
                                    f'<div style="color:#cbd5e1;font-size:0.75rem;">'
                                    f'<strong>Ops Actions:</strong>'
                                    f'<ul style="margin:3px 0 0 14px;padding:0;">'
                                    f'{acts_html}</ul></div>'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )
                            st.markdown('</div>', unsafe_allow_html=True)

                # Clean countries (no threats)
                if _clean:
                    _clean_str = " · ".join(_clean)
                    st.markdown(
                        f'<p style="color:#4b5563;font-size:0.78rem;margin:4px 0 14px 4px;">'
                        f'⚪ No threats: {_clean_str}</p>',
                        unsafe_allow_html=True,
                    )

    # ── Operations Briefing Notes (High-risk only) ───────────────────────────
    _high_list = sorted(
        [t for t in raw_threats if t.get("risk_level") == "High"],
        key=lambda t: t.get("region", ""),
    )
    if _high_list:
        st.markdown("---")
        st.subheader("📋 Operations Briefing Notes — High-Risk Items")
        st.warning(
            f"**{len(_high_list)} High-Risk threat{'s' if len(_high_list) != 1 else ''} "
            "require immediate attention from your regional Operations leads.**"
        )
        for t in _high_list:
            acts = _actions(t.get("phase", ""), "High")
            acts_md = "\n".join(f"   - {a}" for a in acts)
            st.markdown(
                f"**📍 {t.get('country','')}** ({t.get('region','')} · "
                f"{t.get('operational_model','')})\n\n"
                f"> **Competitor:** {t.get('company','')} &nbsp;·&nbsp; "
                f"**Biosimilar:** {t.get('biosimilar','')} &nbsp;·&nbsp; "
                f"**Phase:** {t.get('phase','')} &nbsp;·&nbsp; "
                f"**Est. Launch:** {t.get('est_launch','TBD')}\n\n"
                f"**Recommended Actions:**\n{acts_md}\n\n---",
            )

    elif _total == 0:
        st.markdown("---")
        st.success(
            "✅ **No biosimilar threats detected** in any LR priority market for this report period. "
            "Re-run surveillance to refresh intelligence."
        )

# 8. HISTORY
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🕑 History":
    st.title("🕑 Report History")

    all_reports = get_all_reports()
    if not all_reports:
        st.info("No reports yet.")
        st.stop()

    for rep in all_reports:
        ts = rep.get("run_date", "")[:19].replace("T", " ")
        summary = rep.get("summary", "No summary") or "No summary"
        with st.expander(f"📄 Report #{rep['id']}  —  {ts}"):
            st.write(summary[:500] + ("…" if len(summary) > 500 else ""))
