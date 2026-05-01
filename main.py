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

from db import get_all_reports, get_latest_report, get_report_by_id, get_report_count, init_db, MODEL_FAST, MODEL_FLAGSHIP

# ─── Page config ─────────────────────────────────────────────────────────────
# MUST be the very first Streamlit call in the script.
st.set_page_config(
    page_title="Opdivo Biosimilar Surveillance",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="auto",
)

# ─── Viewport meta tag (critical for iOS Safari) ─────────────────────────────
# Streamlit does not inject width=device-width by default, which causes iOS
# Safari to render a zoomed-out blank page.  Injecting it via st.markdown with
# unsafe_allow_html is the only reliable approach in a deployed Streamlit app.
st.markdown(
    '<meta name="viewport" content="width=device-width, initial-scale=1.0, '
    'maximum-scale=5.0, user-scalable=yes">',
    unsafe_allow_html=True,
)

# ─── Database initialisation ─────────────────────────────────────────────────
# Called unconditionally on every startup — CREATE TABLE IF NOT EXISTS makes it
# fully idempotent (safe to run on every rerun, no-ops if tables already exist).
import logging as _logging
_logging.basicConfig(level=_logging.INFO)
_log = _logging.getLogger(__name__)
try:
    # Initialise DB schema on every startup — safe: uses CREATE TABLE IF NOT EXISTS
    # and ALTER TABLE ADD COLUMN only. No data is ever dropped or deleted.
    # On Railway: mount a persistent Volume at the DB_PATH location so the
    # SQLite file survives redeploys (set DB_PATH env var to e.g. /data/opdivo_reports.db).
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
if "active_job_token" not in st.session_state:
    st.session_state["active_job_token"] = ""
if "active_model" not in st.session_state:
    st.session_state["active_model"] = MODEL_FAST  # default to fast model
if "job_completed_today" not in st.session_state:
    # Set to True after any successful run this session to prevent duplicate runs.
    st.session_state["job_completed_today"] = False
if "last_report" not in st.session_state:
    # Load the most-recent report from DB on first visit; subsequent reruns
    # use this cached copy (no DB hit per rerun).  Invalidated in two places:
    #   1. run_status=="done" handler → after a job completes.
    #   2. Here, on fresh session / login.
    st.session_state["last_report"] = get_latest_report()
if "nav_page" not in st.session_state:
    st.session_state["nav_page"] = "📊 Dashboard"

# ─── Password gate ────────────────────────────────────────────────────────────
# Checked immediately after session state is ready — before CSS, DB, or any UI.
_CORRECT_PASSWORD = "lrbiosim"

if not st.session_state["authenticated"]:
    # Inject minimal CSS so the login card renders correctly even though the
    # full stylesheet hasn't loaded yet.
    st.markdown("""
    <style>
    html, body {
        background-color: #111827 !important;
        color: #e5e7eb !important;
        font-family: 'Inter', 'Segoe UI', sans-serif;
    }
    [data-testid="stApp"],
    [data-testid="stAppViewContainer"],
    .stApp, .appview-container, .main, .block-container {
        background-color: #111827 !important;
        color: #e5e7eb !important;
    }
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] span { color: #e5e7eb !important; }
    /* Mobile: remove Streamlit's default side padding so login card fills screen */
    .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    .stButton > button {
        background: #00D4C8 !important;
        color: #111827 !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        border: none !important;
        width: 100% !important;
        min-height: 48px !important;
    }
    /* Make text inputs tappable on iOS */
    input[type="password"], input[type="text"] {
        font-size: 16px !important;
        min-height: 44px !important;
        background-color: #1f2937 !important;
        color: #e5e7eb !important;
        border-color: #374151 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="display:flex;flex-direction:column;align-items:center;
                justify-content:center;padding:2rem 0;">
      <div style="background:#1f2937;border:1px solid #374151;border-radius:16px;
                  padding:clamp(24px,5vw,48px) clamp(20px,6vw,56px);
                  max-width:420px;width:100%;text-align:center;
                  box-shadow:0 8px 32px rgba(0,0,0,0.5);box-sizing:border-box;">
        <div style="font-size:3rem;margin-bottom:10px;">💊</div>
        <h2 style="color:#f9fafb;margin:0 0 6px 0;font-size:clamp(1.2rem,4vw,1.55rem);font-weight:700;">
          Opdivo Biosimilar Intelligence
        </h2>
        <p style="color:#6b7280;font-size:0.82rem;margin:0 0 6px 0;
                  letter-spacing:0.04em;text-transform:uppercase;">biosimintel.com</p>
        <p style="color:#9ca3af;font-size:0.88rem;margin:0 0 24px 0;line-height:1.5;">
          Restricted Access — Enter Access Code to Continue
        </p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Single-column layout on mobile — no side gutters that crush the input
    with st.container():
        _lcol, _ccol, _rcol = st.columns([1, 4, 1])
    with _ccol:
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

# ─── Custom CSS (dark-mode biotech theme — mobile-first) ─────────────────────
st.markdown("""
<style>
/* ════════════════════════════════════════════════════════
   RESET & BASE — force dark bg + light text everywhere
   Modern Streamlit uses data-testid selectors; [class*="css"]
   is unreliable in 1.30+, so we target every layer explicitly.
   ════════════════════════════════════════════════════════ */
html, body {
    background-color: #111827 !important;
    color: #e5e7eb !important;
    font-family: 'Inter', 'Segoe UI', sans-serif !important;
}

/* Streamlit root app shell */
[data-testid="stApp"],
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"],
.stApp, .appview-container, .main {
    background-color: #111827 !important;
    color: #e5e7eb !important;
}

/* Every generic element inside the app */
[data-testid="stApp"] p,
[data-testid="stApp"] span,
[data-testid="stApp"] div,
[data-testid="stApp"] li,
[data-testid="stApp"] td,
[data-testid="stApp"] th,
[data-testid="stApp"] label {
    color: #e5e7eb !important;
}

/* Markdown containers */
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] a {
    color: #e5e7eb !important;
}

/* Caption / helper text */
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p {
    color: #9ca3af !important;
}

/* Streamlit main container — responsive horizontal padding */
.block-container {
    padding-top: 1.5rem !important;
    padding-left: clamp(0.75rem, 3vw, 3rem) !important;
    padding-right: clamp(0.75rem, 3vw, 3rem) !important;
    max-width: 100% !important;
    background-color: #111827 !important;
}

/* ---- Sidebar ---- */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div {
    background-color: #1f2937 !important;
    border-right: 1px solid #374151;
}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] label {
    color: #e5e7eb !important;
}
/* Radio items in sidebar */
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #e5e7eb !important; }
[data-testid="stSidebarNav"] span { color: #e5e7eb !important; }

/* ---- Form labels / selectbox labels ---- */
[data-testid="stSelectbox"] label,
[data-testid="stMultiSelect"] label,
[data-testid="stTextInput"] label,
[data-testid="stRadio"] label,
[data-testid="stCheckbox"] label,
.stSelectbox label, .stMultiSelect label {
    color: #d1d5db !important;
    font-weight: 500;
}

/* ---- Selectbox / multiselect dropdown text ---- */
[data-baseweb="select"] [data-testid="stMarkdownContainer"],
[data-baseweb="select"] span,
[data-baseweb="select"] div,
[data-baseweb="tag"] span {
    color: #e5e7eb !important;
    background-color: #1f2937 !important;
}
[data-baseweb="menu"] { background-color: #1f2937 !important; }
[data-baseweb="menu"] li { color: #e5e7eb !important; background-color: #1f2937 !important; }
[data-baseweb="menu"] li:hover { background-color: #374151 !important; }

/* ---- Input fields ---- */
[data-baseweb="input"] input,
[data-baseweb="input"] textarea,
[data-testid="stTextInput"] input {
    background-color: #1f2937 !important;
    color: #e5e7eb !important;
    border-color: #374151 !important;
    font-size: 16px !important;   /* prevents iOS auto-zoom */
    min-height: 44px !important;
}

/* ---- st.info / st.warning / st.error / st.success boxes ---- */
[data-testid="stAlert"],
[data-testid="stAlert"] p,
[data-testid="stAlert"] span,
[data-testid="stAlert"] div {
    color: #e5e7eb !important;
}
/* Info box specifically */
[data-testid="stAlert"][kind="info"],
.stAlert[data-baseweb="notification"][kind="info"] {
    background-color: #1e3a5f !important;
    border-color: #3b82f6 !important;
}

/* ---- KPI cards ---- */
.kpi-card {
    background: #1f2937 !important;
    border: 1px solid #374151;
    border-radius: 12px;
    padding: clamp(12px, 3vw, 20px) clamp(10px, 3vw, 24px);
    text-align: center;
    min-width: 0;
    word-break: break-word;
    color: #e5e7eb !important;
}
.kpi-value {
    font-size: clamp(1.4rem, 4vw, 2.2rem) !important;
    font-weight: 700 !important;
    color: #00D4C8 !important;
    line-height: 1.2;
}
.kpi-label {
    font-size: clamp(0.72rem, 2vw, 0.85rem) !important;
    color: #9ca3af !important;
    margin-top: 4px;
}

/* ---- Update / Verified Intelligence cards ---- */
.update-card {
    background: #1f2937 !important;
    border-left: 4px solid #00D4C8;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 12px;
    word-break: break-word;
    color: #e5e7eb !important;
}
.update-card .source { font-size: 0.78rem; color: #9ca3af !important; }
.update-card .title  { font-weight: 600; margin: 4px 0; color: #f9fafb !important; }
.update-card .body   { font-size: 0.9rem; color: #d1d5db !important; }

/* ---- Social post cards ---- */
.post-card {
    background: #1f2937 !important;
    border: 1px solid #374151;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 10px;
    word-break: break-word;
    color: #e5e7eb !important;
}
.post-card .user  { font-weight: 600; color: #60a5fa !important; }
.post-card .time  { font-size: 0.78rem; color: #6b7280 !important; margin-left: 8px; }
.post-card .text  { margin-top: 8px; font-size: 0.9rem; color: #e5e7eb !important; }
.post-card .post-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}
.post-card .post-meta {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}
.post-card .platform-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #111827;
    border: 1px solid #374151;
    color: #d1d5db !important;
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.01em;
}
.post-card .post-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: #93c5fd !important;
    font-size: 0.82rem;
    font-weight: 600;
    text-decoration: none;
}
.post-card .post-link:hover { color: #bfdbfe !important; text-decoration: underline; }

/* ---- Badges ---- */
.badge-pos { background:#065f46 !important; color:#6ee7b7 !important; padding:2px 10px; border-radius:99px; font-size:0.78rem; white-space:nowrap; }
.badge-neu { background:#3b3a1e !important; color:#fde68a !important; padding:2px 10px; border-radius:99px; font-size:0.78rem; white-space:nowrap; }
.badge-neg { background:#7f1d1d !important; color:#fca5a5 !important; padding:2px 10px; border-radius:99px; font-size:0.78rem; white-space:nowrap; }

/* ---- Headings ---- */
h1, h2, h3, h4, h5, h6 {
    color: #f9fafb !important;
}
h1 { font-size: clamp(1.4rem, 5vw, 2rem) !important; }
h2 { font-size: clamp(1.1rem, 4vw, 1.5rem) !important; }
h3 { font-size: clamp(1rem, 3vw, 1.25rem) !important; }

/* ---- Buttons — minimum 44px touch target (Apple HIG) ---- */
.stButton > button {
    background: #00D4C8 !important;
    color: #111827 !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    border: none !important;
    min-height: 44px !important;
    font-size: clamp(0.85rem, 2.5vw, 1rem) !important;
}
.stButton > button:hover { background: #00b8ae !important; }

/* ---- Dataframe — force readable text and dark bg ---- */
.stDataFrame {
    border-radius: 8px;
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch;
}
.stDataFrame table { background-color: #1f2937 !important; }
.stDataFrame th {
    background-color: #111827 !important;
    color: #f9fafb !important;
    border-bottom: 1px solid #374151 !important;
}
.stDataFrame td {
    background-color: #1f2937 !important;
    color: #e5e7eb !important;
    border-color: #374151 !important;
}
[data-testid="stDataFrame"] * { color: #e5e7eb !important; }

/* ---- Tabs — scrollable on mobile ---- */
.stTabs [data-baseweb="tab-list"] {
    background: #1f2937 !important;
    border-radius: 8px;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    flex-wrap: nowrap;
}
.stTabs [data-baseweb="tab"] {
    color: #9ca3af !important;
    white-space: nowrap;
    min-width: fit-content;
    padding: 8px 12px !important;
    font-size: clamp(0.78rem, 2vw, 0.9rem) !important;
}
.stTabs [aria-selected="true"] {
    color: #00D4C8 !important;
    border-bottom-color: #00D4C8 !important;
}

/* ---- Plotly charts ---- */
.js-plotly-plot, .plotly { max-width: 100% !important; }

/* ---- Progress banner grid — stack on mobile ---- */
.banner-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}

/* ════════════════════════════════════════════════════════
   MOBILE  (≤ 640 px)
   ════════════════════════════════════════════════════════ */
@media (max-width: 640px) {
    .block-container {
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
        padding-top: 0.75rem !important;
    }
    .kpi-value { font-size: 1.5rem !important; }
    .kpi-label { font-size: 0.72rem !important; }
    .kpi-card  { padding: 10px 8px; border-radius: 8px; }
    .banner-grid { grid-template-columns: 1fr !important; }
    .stSelectbox, .stRadio { width: 100% !important; }
    .js-plotly-plot .main-svg { width: 100% !important; }
    p, li, td, th { font-size: 0.88rem !important; }
}

/* ════════════════════════════════════════════════════════
   SMALL TABLET  (641 px – 900 px)
   ════════════════════════════════════════════════════════ */
@media (min-width: 641px) and (max-width: 900px) {
    .kpi-value { font-size: 1.7rem !important; }
    .block-container {
        padding-left: 1.25rem !important;
        padding-right: 1.25rem !important;
    }
}
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


def run_surveillance_thread(use_batch: bool, job_token: str, model: str = MODEL_FAST):
    """Runs the surveillance in a background thread so Streamlit doesn't block.

    IMPORTANT: do not mutate Streamlit session state inside this worker thread.
    Session updates can be lost across reruns when written off the script thread.
    The main script reconciles completion/error state from agent status + DB.
    """
    import agent as _agent

    try:
        _agent.run_surveillance(use_batch=use_batch, run_token=job_token, model=model)
    except Exception as exc:
        try:
            _agent.mark_job_error(str(exc))
        except Exception:
            pass


def reconcile_job_state_from_agent() -> bool:
    """Synchronise UI/session state with agent status in the main script thread.

    Returns True when state was changed and an immediate rerun is recommended.
    """
    try:
        import agent as _agent
        _status = _agent.get_status_snapshot()
    except Exception:
        return False

    _phase = _status.get("phase", "idle")
    _detail = _status.get("detail", "")
    _run_token = str(_status.get("run_token", "") or "")
    _result_ready = bool(_status.get("result_ready", False))
    _expected_run_date = str(_status.get("expected_report_run_date", "") or "")
    _active_job_token = str(st.session_state.get("active_job_token", "") or "")
    _changed = False

    # Ignore terminal states from an old run; only reconcile the active job.
    if _active_job_token and _run_token and _run_token != _active_job_token:
        return False

    # If the worker reached finalizing/done/complete, verify DB persistence before
    # clearing the running flag and surfacing the new report.
    if _phase in {"finalizing", "done", "complete"}:
        _start: datetime | None = st.session_state.get("job_start_time")
        _latest = get_latest_report()
        _saved_ok = False

        if _latest and _latest.get("run_date"):
            # Primary check: exact DB marker from the agent after save_report().
            if _result_ready and _expected_run_date:
                _saved_ok = str(_latest.get("run_date", "")) == _expected_run_date
            else:
                # Fallback: any report saved at or after the job started is ours.
                _saved_ok = True
                if _start is not None:
                    try:
                        _saved_at = datetime.fromisoformat(_latest["run_date"])
                        _saved_ok = _saved_at >= _start
                    except Exception:
                        _saved_ok = False

        if _saved_ok:
            # Unconditionally load the latest report from DB and update the cache
            # so the dashboard always renders the new data after this rerun.
            st.session_state["last_report"] = _latest
            _changed = True  # always rerun to surface the new report

            if st.session_state.get("surveillance_running"):
                st.session_state["surveillance_running"] = False
            # Stop the elapsed timer immediately.
            if st.session_state.get("job_start_time") is not None:
                st.session_state["job_start_time"] = None
            # Lock buttons for the rest of this session once a job completes.
            if not st.session_state.get("job_completed_today"):
                st.session_state["job_completed_today"] = True
            if st.session_state.get("run_status") not in ("", None):
                st.session_state["run_status"] = ""
            if st.session_state.get("active_job_token"):
                st.session_state["active_job_token"] = ""

            # Ensure agent phase is "done" so future reconcile passes are no-ops.
            if _phase != "done":
                _agent.mark_job_complete("Complete ✓ — Report saved and ready")

    # Terminal error from worker thread: unblock UI immediately.
    if _phase == "error":
        if st.session_state.get("surveillance_running"):
            st.session_state["surveillance_running"] = False
            _changed = True
        if st.session_state.get("job_start_time") is not None:
            st.session_state["job_start_time"] = None
            _changed = True
        _msg = f"error: {_detail}" if _detail else "error: Surveillance run failed"
        if st.session_state.get("run_status") != _msg:
            st.session_state["run_status"] = _msg
            _changed = True
        if st.session_state.get("active_job_token"):
            st.session_state["active_job_token"] = ""
            _changed = True

    return _changed


# reconcile_job_state_from_agent() is NOT called at the top level.
# Calling it unconditionally causes an infinite st.rerun() loop because
# JOB_STATUS["phase"] persists as "done" for the lifetime of the server
# process, making the function return _changed=True on every page load.
# It is called safely inside the progress banner block below, which is
# guarded by `if st.session_state["surveillance_running"]:` — so it only
# ever executes while a job is genuinely in flight.


# (Session state and password gate have already run at the top of the file.)


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💊 Opdivo Surveillance")
    st.markdown("---")

    _NAV_OPTIONS = [
        "📊 Dashboard",
        "🔬 Pipeline Tracker",
        "✅ Verified Intelligence",
        "📣 Social Noise",
        "🤖 AI Insights",
        "📅 Timeline",
        "🌍 LR Markets",
        "🕑 History",
    ]
    # Honour a programmatic navigation request (e.g. "View History" link)
    if st.session_state.get("_goto_page"):
        st.session_state["nav_page"] = st.session_state.pop("_goto_page")
    page = st.radio(
        "Navigation",
        _NAV_OPTIONS,
        label_visibility="collapsed",
        key="nav_page",
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
            _job_token = datetime.now().isoformat()
            st.session_state["surveillance_running"] = True
            st.session_state["run_status"] = "running"
            st.session_state["job_start_time"] = datetime.fromisoformat(_job_token)
            st.session_state["active_job_token"] = _job_token
            st.session_state["active_model"] = MODEL_FAST
            t = threading.Thread(
                target=run_surveillance_thread,
                args=(use_batch, _job_token, MODEL_FAST),
                daemon=True,
            )
            t.start()
            st.rerun()   # immediately re-render so the button disables right away

    # ── Flagship Run (access-code protected) ───────────────────────────────
    _FLAGSHIP_CODE = "flagship2026"
    with st.expander("🚀 Run Flagship Model", expanded=False):
        st.caption("Higher accuracy · Significantly slower · Requires access code")
        _fs_code = st.text_input("Access code", type="password", key="_flagship_code_input", label_visibility="collapsed", placeholder="Enter access code")
        _fs_clicked = st.button(
            "🚀 Run Flagship",
            disabled=job_running,
            use_container_width=True,
            key="_flagship_btn",
        )
        if _fs_clicked:
            if st.session_state["surveillance_running"]:
                st.warning("⚠️ A job is already running.")
            elif _fs_code != _FLAGSHIP_CODE:
                st.error("❌ Invalid access code.")
            else:
                _job_token = datetime.now().isoformat()
                st.session_state["surveillance_running"] = True
                st.session_state["run_status"] = "running"
                st.session_state["job_start_time"] = datetime.fromisoformat(_job_token)
                st.session_state["active_job_token"] = _job_token
                st.session_state["active_model"] = MODEL_FLAGSHIP
                t = threading.Thread(
                    target=run_surveillance_thread,
                    args=(use_batch, _job_token, MODEL_FLAGSHIP),
                    daemon=True,
                )
                t.start()
                st.rerun()

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
        _mv = _cached.get("model_version") or MODEL_FAST
        _mv_label = "⚡ Grok 4.1 Fast" if _mv == MODEL_FAST else "🚀 Grok 4.20 Flagship"
        _mv_color = "#6b7280" if _mv == MODEL_FAST else "#fbbf24"
        st.markdown(
            f'<div style="background:#1f2937;border:1px solid #374151;border-radius:8px;'
            f'padding:10px 12px;font-size:0.80rem;color:#9ca3af;line-height:1.6;">'
            f'<b style="color:#d1d5db;">📄 Cached Report</b><br>'
            f'{_ts}<br>'
            f'<span style="color:{_mv_color};font-size:0.75rem;">{_mv_label}</span>&nbsp;'
            f'<span style="color:#6b7280;">{_age_str}</span></div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("No report yet. Click ▶ Run Now.")

    st.markdown("---")
    # ── Test Email ─────────────────────────────────────────────────────────
    if st.button(
        "🧪 Send Test Email",
        use_container_width=True,
        help="Send a synthetic high-risk alert to verify the email system",
    ):
        with st.spinner("Sending test email…"):
            try:
                from notifications import send_test_email as _send_test
                _send_test()
                st.success("✅ Test email sent! Check your inbox.")
            except Exception as _te:
                st.error(f"❌ Test email failed: {_te}")

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

    import time as _time

    _use_batch = "Batch" in st.session_state.get("run_mode_select", "Batch")
    _eta = "15 – 90 minutes" if _use_batch else "5 – 20 minutes"
    _mode_label = "Batch API (50% cheaper)" if _use_batch else "Synchronous API"
    _close_note = (
        "You can safely close this tab — the job runs in the background and the dashboard will update automatically when ready."
        if _use_batch
        else "Keep this tab open until the job finishes."
    )

    # ── Safe job-completion check (only runs because surveillance_running is True) ──
    # reconcile_job_state_from_agent() inspects the agent's JOB_STATUS phase.
    # If the worker has finished (phase in {done, complete, finalizing} + DB
    # row verified), it: loads the latest report into last_report, clears
    # surveillance_running / job_start_time / run_status / active_job_token,
    # and returns True.  We then rerun once so the dashboard renders the new
    # report immediately without the user having to refresh.
    # This is safe here because the entire block is guarded by
    # `if st.session_state["surveillance_running"]:` above — so the function
    # only ever executes while a job is genuinely in flight.
    if reconcile_job_state_from_agent():
        st.rerun()

    # Read live phase from agent module (set by worker thread)
    try:
        import agent as _agent_mod
        _status      = _agent_mod.get_status_snapshot()
        _job_phase   = _status.get("phase", "running")
        _job_detail  = _status.get("detail", "")
    except Exception:
        _job_phase  = "running"
        _job_detail = ""

    _PHASE_LABELS = {
        "idle":        "Waiting to start",
        "starting":    "Initialising…",
        "connecting":  "Connecting to AI…",
        "submitting":  "Submitting batch job…",
        "queued":      "Job queued — awaiting processing",
        "waiting":     "Waiting for AI response…",
        "polling":     "Polling batch — awaiting completion…",
        "retrieving":  "Downloading results…",
        "received":    "Response received — parsing…",
        "parsing":     "Parsing JSON response…",
        "saving":      "Saving report to database…",
        "emailing":    "Sending email alert…",
        "finalizing":  "Final checks — verifying saved report…",
        "done":        "Complete ✓",
        "error":       "Status error",
    }
    _phase_display = _PHASE_LABELS.get(_job_phase, _job_phase.replace("_", " ").title())
    if _job_detail:
        _status_line = f"{_phase_display} — {_job_detail}"
    else:
        _status_line = _phase_display

    # ── Cycling informative messages (rotate every 10 seconds) ──────────────
    _CYCLE_MSGS = [
        ("🔬", "Analyzing global biosimilar pipeline data…"),
        ("📋", "Scanning regulatory filings across LR markets…"),
        ("🌍", "Evaluating threats in your priority countries…"),
        ("📅", "Assessing launch probabilities and timelines…"),
        ("📊", "Compiling actionable insights for Operations teams…"),
        ("🧬", "Cross-referencing clinical trial data…"),
        ("📡", "Monitoring social and market sentiment…"),
        ("🏭", "Mapping biosimilar manufacturing landscapes…"),
        ("⚖️",  "Reviewing patent expiry and litigation signals…"),
        ("📈", "Benchmarking competitive pricing intelligence…"),
    ]
    _cycle_idx   = int(_time.time() // 10) % len(_CYCLE_MSGS)
    _cycle_icon, _cycle_msg = _CYCLE_MSGS[_cycle_idx]

    st.markdown(
        f"""
<div style="
  background: linear-gradient(160deg,#0d1f1a 0%,#0f2d22 60%,#0d1f1a 100%);
  border: 2px solid #16a34a;
  border-radius: 20px;
  padding: 44px 48px 36px;
  margin-bottom: 32px;
  box-shadow: 0 8px 48px rgba(22,163,74,0.18), 0 2px 8px rgba(0,0,0,0.5);
">

  <!-- Header -->
  <div style="display:flex;align-items:flex-start;gap:18px;margin-bottom:28px;">
    <div style="font-size:2.8rem;line-height:1;flex-shrink:0;">🛰️</div>
    <div>
      <div style="color:#4ade80;font-size:1.5rem;font-weight:800;letter-spacing:-0.02em;line-height:1.2;">
        Surveillance Job Running
      </div>
      <div style="color:#86efac;font-size:0.92rem;margin-top:6px;">
        Mode: <b style="color:#a7f3d0;">{_mode_label}</b>
        &nbsp;·&nbsp; This Batch job uses AI and typically takes <b style="color:#a7f3d0;">{_eta}</b>.
      </div>
    </div>
  </div>

  <!-- Stats grid -->
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:22px;">
    <div style="background:rgba(20,83,45,0.35);border:1px solid #166534;border-radius:12px;padding:18px 20px;">
      <div style="color:#86efac;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.09em;margin-bottom:6px;">⏱ Job Running For</div>
      <div style="color:#f0fdf4;font-size:1.75rem;font-weight:800;letter-spacing:-0.02em;">{_elapsed_str}</div>
    </div>
    <div style="background:rgba(20,83,45,0.35);border:1px solid #166534;border-radius:12px;padding:18px 20px;">
      <div style="color:#86efac;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.09em;margin-bottom:6px;">⏳ Estimated Duration</div>
      <div style="color:#f0fdf4;font-size:1.1rem;font-weight:700;">{_eta}</div>
    </div>
    <div style="background:rgba(20,83,45,0.35);border:1px solid #166534;border-radius:12px;padding:18px 20px;">
      <div style="color:#86efac;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.09em;margin-bottom:6px;">📡 Current Phase</div>
      <div style="color:#4ade80;font-size:0.88rem;font-weight:600;line-height:1.4;">{_status_line}</div>
    </div>
  </div>

  <!-- Cycling activity message -->
  <div style="background:rgba(5,46,22,0.7);border:1px solid #15803d;border-radius:12px;
              padding:18px 22px;margin-bottom:18px;display:flex;align-items:center;gap:14px;">
    <div style="font-size:1.7rem;flex-shrink:0;">{_cycle_icon}</div>
    <div>
      <div style="color:#bbf7d0;font-size:1.0rem;font-weight:600;">{_cycle_msg}</div>
      <div style="color:#6ee7b7;font-size:0.78rem;margin-top:3px;">Processing step {_cycle_idx + 1} of {len(_CYCLE_MSGS)} · updates every 10 seconds</div>
    </div>
  </div>

  <!-- Info footer -->
  <div style="background:rgba(17,24,39,0.6);border:1px solid #374151;border-radius:10px;
              padding:14px 18px;color:#9ca3af;font-size:0.86rem;line-height:1.8;">
    <span style="color:#6ee7b7;">💡</span> <b style="color:#d1fae5;">{_close_note}</b><br>
    <span style="color:#6ee7b7;">🔄</span> This page auto-refreshes every 30 seconds — new results appear automatically when ready.<br>
    <span style="color:#6ee7b7;">🚫</span> The <b style="color:#d1fae5;">Run Now</b> button is locked until this job completes.
  </div>

</div>
""",
        unsafe_allow_html=True,
    )

    # Poll every 5 s while the job is still in flight so the UI stays
    # responsive.  (The fast-path above exits immediately on completion.)
    if _job_phase not in {"done", "complete", "error"}:
        _time.sleep(5)
    st.rerun()

# ─── Page routing ─────────────────────────────────────────────────────────────

# ══════════════════════════════════════════════════════════════════════════════
# 1. DASHBOARD OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
if page == "📊 Dashboard":
    st.title("📊 Dashboard Overview")
    st.caption("Opdivo (nivolumab) biosimilar competitive intelligence — Powered by AI")

    if not data:
        st.warning("No report found. Use the sidebar to run a new surveillance sweep.")
        st.stop()

    # ── Latest-report info strip ────────────────────────────────────────────
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
            _strip_col, _hist_col = st.columns([6, 1])
            with _strip_col:
                st.markdown(
                    f'<div style="background:#1f2937;border:1px solid #374151;border-radius:8px;'
                    f'padding:9px 16px;font-size:0.82rem;color:#9ca3af;line-height:1.7;">'
                    f'<span style="color:#00D4C8;font-size:1rem;">📋</span>&nbsp;'
                    f'Showing <b style="color:#d1d5db;">latest report</b> from '
                    f'<b style="color:#f9fafb;">{_rpt_ts}</b>'
                    f'&nbsp;<span style="color:#6b7280;">({_rpt_age_str})</span>'
                    f'&nbsp;·&nbsp;<span style="color:#4b5563;">'
                    f'Run a new sweep to refresh.</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with _hist_col:
                if st.button("🕑 History", use_container_width=True, key="_dash_view_history"):
                    st.session_state["_goto_page"] = "🕑 History"
                    st.rerun()
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

    # On mobile Streamlit stacks narrow columns automatically; gap=True adds
    # breathing room between cards at all screen sizes.
    kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6, gap="small")

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
    # Filter row — collapses gracefully on narrow screens
    fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 3], gap="small")
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

    left, right = st.columns([7, 3], gap="small")

    with left:
        sent_filter = st.multiselect("Filter by sentiment", ["Positive", "Neutral", "Negative"])
        posts = [p for p in social if (not sent_filter or p.get("sentiment") in sent_filter)]
        for post in posts:
            _post_url = (post.get("url") or "").strip()
            _url_verified = bool(post.get("url_verified", False))
            _platform = (post.get("platform") or "News").strip()
            if _post_url and _url_verified:
                _link_html = (
                    f'<a class="post-link" href="{_post_url}" target="_blank" rel="noopener noreferrer">'
                    f'🔗 View Original</a>'
                )
            elif _post_url and not _url_verified:
                # URL present but not confirmed — do not render as clickable
                _link_html = '<span style="font-size:0.78rem;color:#6b7280;">⚠️ Source link unverified</span>'
            else:
                _link_html = '<span style="font-size:0.78rem;color:#6b7280;">No verifiable link available</span>'
            st.markdown(
                f'<div class="post-card">'
                f'<div class="post-header">'
                f'<div class="post-meta">'
                f'<span class="platform-badge">🌐 {_platform}</span>'
                f'<span class="user">{post.get("user","@unknown")}</span>'
                f'<span class="time">{post.get("date","")}</span>'
                f'{sentiment_badge(post.get("sentiment","Neutral"))}'
                f'</div>'
                f'{_link_html}'
                f'</div>'
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
    st.subheader("AI Deep Reasoning")
    st.markdown(ai_insights or "No AI insights available in this report.", unsafe_allow_html=False)

    st.markdown("---")
    st.subheader("Competitive Risk Heatmap")

    if not companies:
        st.info("No risk data available yet. Run a new surveillance sweep.")
    else:
        my_threats = data.get("my_markets_threat", []) if data else []

        def _clamp(v: int | float, lo: int = 0, hi: int = 100) -> int:
            try:
                return max(lo, min(hi, int(v)))
            except Exception:
                return lo

        def _phase_risk_score(phase: str) -> int:
            p = (phase or "").lower()
            if "launch" in p:
                return 95
            if "approved" in p:
                return 80
            if "bla" in p or "file" in p or "submitted" in p:
                return 70
            if "phase iii" in p or "phase 3" in p:
                return 60
            if "phase ii" in p or "phase 2" in p:
                return 45
            if "phase i" in p or "phase 1" in p:
                return 30
            if "pre" in p:
                return 15
            return 35

        def _lr_risk_score(company_name: str, probability: int) -> int:
            risk_map = {"low": 25, "medium": 60, "high": 90}
            key = (company_name or "").lower().split()[0] if company_name else ""
            matched_scores: list[int] = []
            for t in my_threats:
                competitor = str(t.get("competitor", "")).lower()
                if key and key in competitor:
                    level = str(t.get("risk_level", "")).strip().lower()
                    matched_scores.append(risk_map.get(level, 50))

            # Use explicit LR threat risk when available; fallback to weighted proxy.
            if matched_scores:
                return max(matched_scores)
            return _clamp(round(probability * 0.7 + 20), 15, 85)

        records: list[dict] = []
        for c in companies:
            company = c.get("company", "Unknown")
            prob = _clamp(c.get("probability", 0))
            lr_risk = _lr_risk_score(company, prob)
            phase_risk = _phase_risk_score(c.get("phase", ""))
            records.append(
                {
                    "Company": company,
                    "Probability Risk": prob,
                    "Risk to LR Markets": lr_risk,
                    "Phase Risk": phase_risk,
                }
            )

        risk_df = pd.DataFrame(records)
        if risk_df.empty:
            st.info("No risk data available yet. Run a new surveillance sweep.")
        else:
            # Prioritise highest-risk companies at the top.
            risk_df["_rank"] = risk_df[["Probability Risk", "Risk to LR Markets", "Phase Risk"]].max(axis=1)
            risk_df = risk_df.sort_values("_rank", ascending=False).drop(columns=["_rank"])

            z = risk_df[["Probability Risk", "Risk to LR Markets", "Phase Risk"]].values
            fig_heat = go.Figure(
                data=go.Heatmap(
                    z=z,
                    x=["Probability", "Risk to LR Markets", "Phase Risk"],
                    y=risk_df["Company"].tolist(),
                    zmin=0,
                    zmax=100,
                    colorscale=[
                        [0.0, "#10b981"],   # Low = green
                        [0.5, "#f59e0b"],   # Medium = amber
                        [1.0, "#ef4444"],   # High = red
                    ],
                    colorbar=dict(
                        title="Risk",
                        tickvals=[20, 50, 85],
                        ticktext=["Low", "Medium", "High"],
                    ),
                    hovertemplate=(
                        "<b>%{y}</b><br>"
                        "%{x}: %{z:.0f}<extra></extra>"
                    ),
                )
            )
            fig_heat.update_layout(
                template="plotly_dark",
                paper_bgcolor="#111827",
                plot_bgcolor="#1f2937",
                margin=dict(t=10, b=10, l=10, r=10),
                height=max(280, 42 * len(risk_df)),
                yaxis=dict(autorange="reversed"),
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

    sk1, sk2, sk3, sk4 = st.columns(4, gap="small")
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

    # Handle "Load Report" action from a row button
    _load_id = st.session_state.pop("_load_report_id", None)
    if _load_id:
        _loaded = get_report_by_id(_load_id)
        if _loaded:
            st.session_state["last_report"] = _loaded
            st.session_state["_goto_page"] = "📊 Dashboard"
            st.rerun()

    all_reports = get_all_reports()
    if not all_reports:
        st.info("No reports yet. Run a surveillance job to generate your first report.")
        st.stop()

    # ── Summary counts ──────────────────────────────────────────────────────
    _fast_count = sum(1 for r in all_reports if (r.get("model_version") or MODEL_FAST) == MODEL_FAST)
    _flag_count = len(all_reports) - _fast_count
    _c1, _c2, _c3 = st.columns(3)
    _c1.metric("📊 Total Reports", len(all_reports))
    _c2.metric("⚡ Grok 4.1 Fast", _fast_count)
    _c3.metric("🚀 Grok 4.20 Flagship", _flag_count)
    st.caption("Click **Load** to view any historical report on the Dashboard for side-by-side comparison.")
    st.markdown("---")

    for rep in all_reports:
        ts = rep.get("run_date", "")[:19].replace("T", " ")
        summary = rep.get("summary", "No summary") or "No summary"
        mv = rep.get("model_version") or MODEL_FAST
        is_flagship = mv == MODEL_FLAGSHIP
        if is_flagship:
            _badge_html = '<span style="background:#78350f;color:#fbbf24;border-radius:4px;padding:2px 8px;font-size:0.72rem;font-weight:700;letter-spacing:0.02em;">🚀 Grok 4.20 Flagship</span>'
            _border_color = "#92400e"
        else:
            _badge_html = '<span style="background:#1e3a5f;color:#93c5fd;border-radius:4px;padding:2px 8px;font-size:0.72rem;font-weight:700;letter-spacing:0.02em;">⚡ Grok 4.1 Fast</span>'
            _border_color = "#1e40af"

        col_exp, col_btn = st.columns([9, 1])
        with col_exp:
            with st.expander(f"📄 Report #{rep['id']}  —  {ts}"):
                st.markdown(_badge_html, unsafe_allow_html=True)
                st.caption(f"Model: `{mv}`")
                st.write(summary[:600] + ("…" if len(summary) > 600 else ""))
        with col_btn:
            if st.button("Load", key=f"_load_{rep['id']}", use_container_width=True, help="Load this report onto the Dashboard"):
                st.session_state["_load_report_id"] = rep["id"]
                st.rerun()
