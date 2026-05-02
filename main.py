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

import html
import json
import logging as _logging
import os
import threading
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from db import get_all_reports, get_latest_report, get_report_by_id, init_db, MODEL_FAST
from theme import _PRESENTATION_CSS, _DARK_CSS

# ─── Global thread tracker (prevents multiple concurrent surveillance jobs) ───
_ACTIVE_THREAD: threading.Thread | None = None

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
if "theme" not in st.session_state:
    st.session_state["theme"] = "presentation"

# ─── Password gate ────────────────────────────────────────────────────────────
# Checked immediately after session state is ready — before CSS, DB, or any UI.
_CORRECT_PASSWORD = os.getenv("ACCESS_CODE", "1001")

if not st.session_state["authenticated"]:
    # Inject minimal CSS so the login card renders correctly even though the
    # full stylesheet hasn't loaded yet.
    _is_pres = st.session_state.get("theme", "presentation") == "presentation"
    if _is_pres:
        st.markdown("""
        <style>
        html, body {
            background-color: #F8F9FA !important;
            color: #1A202C !important;
            font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        [data-testid="stApp"],
        [data-testid="stAppViewContainer"],
        .stApp, .appview-container, .main, .block-container {
            background-color: #F8F9FA !important;
            color: #1A202C !important;
        }
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] span { color: #1A202C !important; }
        .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
        .stButton > button {
            background: #0F766E !important;
            color: #FFFFFF !important;
            font-weight: 600 !important;
            border-radius: 8px !important;
            border: none !important;
            width: 100% !important;
            min-height: 48px !important;
        }
        input[type="password"], input[type="text"] {
            font-size: 16px !important;
            min-height: 44px !important;
            background-color: #FFFFFF !important;
            color: #1A202C !important;
            border-color: #CBD5E0 !important;
        }
        </style>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div style="display:flex;flex-direction:column;align-items:center;
                    justify-content:center;padding:2rem 0;">
          <div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:16px;
                      padding:clamp(24px,5vw,48px) clamp(20px,6vw,56px);
                      max-width:420px;width:100%;text-align:center;
                      box-shadow:0 4px 16px rgba(0,0,0,0.08);box-sizing:border-box;">
            <div style="font-size:3rem;margin-bottom:10px;">💊</div>
            <h2 style="color:#1A202C;margin:0 0 6px 0;font-size:clamp(1.2rem,4vw,1.55rem);font-weight:700;">
              Opdivo Biosimilar Intelligence
            </h2>
            <p style="color:#4A5568;font-size:0.85rem;margin:0 0 6px 0;
                      letter-spacing:0.04em;text-transform:uppercase;">biosimintel.com</p>
            <p style="color:#4A5568;font-size:0.95rem;margin:0 0 24px 0;line-height:1.5;">
              Restricted Access — Enter Access Code to Continue
            </p>
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <style>
        html, body {
            background-color: #0F172A !important;
            color: #F1F5F9 !important;
            font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        [data-testid="stApp"],
        [data-testid="stAppViewContainer"],
        .stApp, .appview-container, .main, .block-container {
            background-color: #0F172A !important;
            color: #F1F5F9 !important;
        }
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] span { color: #F1F5F9 !important; }
        .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
        .stButton > button {
            background: #2DD4BF !important;
            color: #0F172A !important;
            font-weight: 600 !important;
            border-radius: 8px !important;
            border: none !important;
            width: 100% !important;
            min-height: 48px !important;
        }
        input[type="password"], input[type="text"] {
            font-size: 16px !important;
            min-height: 44px !important;
            background-color: #1E293B !important;
            color: #F1F5F9 !important;
            border-color: #475569 !important;
        }
        </style>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div style="display:flex;flex-direction:column;align-items:center;
                    justify-content:center;padding:2rem 0;">
          <div style="background:#1E293B;border:1px solid #334155;border-radius:16px;
                      padding:clamp(24px,5vw,48px) clamp(20px,6vw,56px);
                      max-width:420px;width:100%;text-align:center;
                      box-shadow:0 8px 32px rgba(0,0,0,0.5);box-sizing:border-box;">
            <div style="font-size:3rem;margin-bottom:10px;">💊</div>
            <h2 style="color:#F8FAFC;margin:0 0 6px 0;font-size:clamp(1.2rem,4vw,1.55rem);font-weight:700;">
              Opdivo Biosimilar Intelligence
            </h2>
            <p style="color:#94A3B8;font-size:0.85rem;margin:0 0 6px 0;
                      letter-spacing:0.04em;text-transform:uppercase;">biosimintel.com</p>
            <p style="color:#CBD5E1;font-size:0.95rem;margin:0 0 24px 0;line-height:1.5;">
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

# ─── Theme CSS injection ──────────────────────────────────────────────────────
if st.session_state.get("theme", "presentation") == "presentation":
    st.markdown(_PRESENTATION_CSS, unsafe_allow_html=True)
    _PLOTLY_TEMPLATE = "plotly_white"
    _PLOTLY_PAPER_BG = "#F8F9FA"
    _PLOTLY_PLOT_BG = "#FFFFFF"
    _PLOTLY_FONT_COLOR = "#1A202C"
else:
    st.markdown(_DARK_CSS, unsafe_allow_html=True)
    _PLOTLY_TEMPLATE = "plotly_dark"
    _PLOTLY_PAPER_BG = "#0F172A"
    _PLOTLY_PLOT_BG = "#1E293B"
    _PLOTLY_FONT_COLOR = "#F1F5F9"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _esc(s: object) -> str:
    """Escape HTML entities in user-provided strings to prevent XSS."""
    return html.escape(str(s), quote=True) if s is not None else ""


def _model_tag(model_version: str) -> str:
    """Return a short display tag for a model version string."""
    mv = model_version.lower()
    if "grok" in mv:
        return "Grok"
    if "claude" in mv:
        return "Claude"
    if "gpt" in mv:
        return "GPT"
    if "gemini" in mv:
        return "Gemini"
    if "deepseek" in mv:
        return "DeepSeek"
    return "Legacy"


def _model_badge(model_version: str) -> tuple[str, str]:
    """Return (badge_html, border_color) for a model version."""
    tag = _model_tag(model_version)
    colors = {
        "Grok": ("#0F766E", "#FFFFFF"),
        "Claude": ("#7C3AED", "#FFFFFF"),
        "GPT": ("#2563EB", "#FFFFFF"),
        "Gemini": ("#1A73E8", "#FFFFFF"),
        "DeepSeek": ("#EA580C", "#FFFFFF"),
        "Legacy": ("#6B7280", "#FFFFFF"),
    }
    bg, fg = colors.get(tag, ("#6B7280", "#FFFFFF"))
    badge = (
        f'<span style="background:{bg};color:{fg};border-radius:4px;'
        f'padding:2px 8px;font-size:0.72rem;font-weight:700;letter-spacing:0.02em;">'
        f'{tag}</span>'
    )
    return badge, bg


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

    _start = st.session_state.get("job_start_time")
    if _start and (datetime.now() - _start).total_seconds() > 18000:  # 5 hours
        st.session_state["surveillance_running"] = False
        st.session_state["run_status"] = "error: Job timed out (5h max)"
        st.session_state["job_start_time"] = None
        return True

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
        "🎯 Competitor Pipeline",
        "✅ Verified Intelligence",
        "📣 Social Noise",
        "🤖 AI Insights",
        "📅 Timeline",
        "🌍 LR Markets",
        "🕑 History",
        "🧪 Model Lab",
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

    # ── Model selection + Flagship Run ─────────────────────────────────────
    _FLAGSHIP_CODE = os.getenv("FLAGSHIP_CODE", "flagship2026")
    _MODEL_OPTIONS = {
        "🚀 Grok 4.20 Reasoning (xAI — Live web + X)": "grok-4.20-reasoning",
        "🧠 Claude Sonnet 4.5 (OpenRouter)": "anthropic/claude-sonnet-4.5",
        "🔍 Gemini 2.5 Pro (OpenRouter — Live Google Search)": "google/gemini-2.5-pro-preview-03-25",
        "💡 DeepSeek V4 Pro (OpenRouter)": "deepseek/deepseek-v4-pro",
    }
    _MODEL_DISPLAY = list(_MODEL_OPTIONS.keys())
    _selected_display = st.selectbox(
        "🤖 Select Analysis Model",
        _MODEL_DISPLAY,
        index=0,
        key="_model_select",
    )
    _selected_model = _MODEL_OPTIONS[_selected_display]
    st.session_state["selected_model"] = _selected_model

    if _selected_model.startswith("grok-"):
        st.caption("✅ Live web & X search enabled")
    else:
        st.caption("⚠️ Training data only — no live search")

    _fs_code = st.text_input(
        "🔑 Flagship Access Code",
        type="password",
        key="_flagship_code_input",
        placeholder="Enter code to unlock Run Flagship",
    )
    st.session_state["flagship_code_input"] = _fs_code

    # Real-time validation hint
    if _fs_code and _fs_code != _FLAGSHIP_CODE:
        st.error("❌ Invalid Flagship code")

    _code_ok = _fs_code == _FLAGSHIP_CODE
    _fs_clicked = st.button(
        "🚀 Run Flagship",
        disabled=job_running or not _code_ok,
        use_container_width=True,
        key="_flagship_btn",
    )
    if _fs_clicked:
        if st.session_state["surveillance_running"]:
            st.warning("⚠️ A job is already running.")
        elif _fs_code != _FLAGSHIP_CODE:
            st.error("❌ Invalid Flagship code")
        else:
            if _ACTIVE_THREAD is not None and _ACTIVE_THREAD.is_alive():
                st.warning("A surveillance job is already running. Please wait.")
                st.rerun()
            else:
                _job_token = datetime.now().isoformat()
                st.session_state["surveillance_running"] = True
                st.session_state["run_status"] = "running"
                st.session_state["job_start_time"] = datetime.fromisoformat(_job_token)
                st.session_state["active_job_token"] = _job_token
                st.session_state["active_model"] = _selected_model
                _ACTIVE_THREAD = threading.Thread(
                    target=run_surveillance_thread,
                    args=(False, _job_token, _selected_model),
                    daemon=True,
                )
                _ACTIVE_THREAD.start()
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
        _chip_pres = st.session_state.get("theme", "presentation") == "presentation"
        _chip_bg = "#F0FDFA" if _chip_pres else "#14532d"
        _chip_border = "#99F6E4" if _chip_pres else "#166534"
        _chip_text = "#115E59" if _chip_pres else "#bbf7d0"
        _chip_bold = "#0F766E" if _chip_pres else "#4ade80"
        _chip_sub = "#4A5568" if _chip_pres else "#86efac"
        st.markdown(
            f'<div style="background:{_chip_bg};border:1px solid {_chip_border};border-radius:8px;'
            f'padding:10px 12px;font-size:0.82rem;color:{_chip_text};line-height:1.6;">'
            f'<b style="color:{_chip_bold};">⚙️ Job running</b><br>'
            f'🕐 {elapsed_str} elapsed<br>'
            f'<span style="color:{_chip_sub};">See main area for details.</span></div>',
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
        _mv_tag = _model_tag(_mv)
        _mv_label = f"🤖 {_mv_tag}"
        _mv_color_map = {
            "Grok": "#0F766E",
            "Claude": "#7C3AED",
            "GPT": "#2563EB",
            "DeepSeek": "#EA580C",
            "Legacy": "#6B7280",
        }
        _mv_color = _mv_color_map.get(_mv_tag, "#6b7280")
        _chip_pres = st.session_state.get("theme", "presentation") == "presentation"
        _chip_bg = "#FFFFFF" if _chip_pres else "#1f2937"
        _chip_border = "#E2E8F0" if _chip_pres else "#374151"
        _chip_text = "#4A5568" if _chip_pres else "#9ca3af"
        _chip_bold = "#1A202C" if _chip_pres else "#d1d5db"
        _chip_age = "#718096" if _chip_pres else "#6b7280"
        st.markdown(
            f'<div style="background:{_chip_bg};border:1px solid {_chip_border};border-radius:8px;'
            f'padding:10px 12px;font-size:0.80rem;color:{_chip_text};line-height:1.6;">'
            f'<b style="color:{_chip_bold};">📄 Cached Report</b><br>'
            f'{_ts}<br>'
            f'<span style="color:{_mv_color};font-size:0.75rem;">{_mv_label}</span>&nbsp;'
            f'<span style="color:{_chip_age};">{_age_str}</span></div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("No report yet. Click 🚀 Run Flagship.")

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
    _theme_options = ["🖥️ Presentation Mode", "🌙 Dark Mode"]
    _theme_index = 0 if st.session_state.get("theme", "presentation") == "presentation" else 1
    _selected_theme = st.radio(
        "Theme",
        _theme_options,
        index=_theme_index,
        label_visibility="collapsed",
        key="_theme_radio",
    )
    if _selected_theme == "🖥️ Presentation Mode" and st.session_state.get("theme") != "presentation":
        st.session_state["theme"] = "presentation"
        st.rerun()
    elif _selected_theme == "🌙 Dark Mode" and st.session_state.get("theme") != "dark":
        st.session_state["theme"] = "dark"
        st.rerun()

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
        _elapsed_s = 0
        _elapsed_str = "just started"

    import time as _time

    _eta = "~5 – 20 minutes"
    _close_note = (
        "You can safely close this tab — the job runs in the background and the dashboard will update automatically when ready."
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
        "submitting":  "Submitting surveillance job…",
        "queued":      "Job queued — awaiting processing",
        "waiting":     "Waiting for AI response…",
        "polling":     "Processing — awaiting response…",
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

    # ── Cycling informative messages (rotate every 30 seconds) ──────────────
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
    _cycle_idx   = (_elapsed_s // 30) % len(_CYCLE_MSGS)
    _cycle_icon, _cycle_msg = _CYCLE_MSGS[_cycle_idx]

    # Time-based progress (assumes 90min typical, caps at 95% to avoid false completion)
    _progress = min(_elapsed_s / 5400, 0.95)  # 5400s = 90min
    st.progress(_progress, text=f"⏳ Surveillance in progress — {_elapsed_str} elapsed")

    _is_pres_banner = st.session_state.get("theme", "presentation") == "presentation"
    if _is_pres_banner:
        _BANNER_BG = "#FFFFFF"
        _BANNER_BORDER = "#0F766E"
        _BANNER_SHADOW = "0 4px 24px rgba(15,118,110,0.12), 0 1px 4px rgba(0,0,0,0.06)"
        _TITLE_COLOR = "#0F766E"
        _SUBTITLE_COLOR = "#4A5568"
        _STAT_BG = "#F7FAFC"
        _STAT_BORDER = "#E2E8F0"
        _STAT_LABEL = "#4A5568"
        _STAT_VALUE = "#1A202C"
        _PHASE_COLOR = "#0F766E"
        _CYCLE_BG = "#F0FDFA"
        _CYCLE_BORDER = "#99F6E4"
        _CYCLE_TITLE = "#115E59"
        _CYCLE_SUB = "#4A5568"
        _FOOTER_BG = "#F8F9FA"
        _FOOTER_BORDER = "#E2E8F0"
        _FOOTER_TEXT = "#4A5568"
        _FOOTER_ACCENT = "#0F766E"
        _FOOTER_BOLD = "#1A202C"
        _PULSE_CSS_BANNER = """
<style>
@keyframes pulse-border {
  0% { box-shadow: 0 0 0 0 rgba(15, 118, 110, 0.3); }
  70% { box-shadow: 0 0 0 10px rgba(15, 118, 110, 0); }
  100% { box-shadow: 0 0 0 0 rgba(15, 118, 110, 0); }
}
</style>
"""
    else:
        _BANNER_BG = "linear-gradient(160deg,#0d1f1a 0%,#0f2d22 60%,#0d1f1a 100%)"
        _BANNER_BORDER = "#16a34a"
        _BANNER_SHADOW = "0 8px 48px rgba(22,163,74,0.18), 0 2px 8px rgba(0,0,0,0.5)"
        _TITLE_COLOR = "#4ade80"
        _SUBTITLE_COLOR = "#86efac"
        _STAT_BG = "rgba(20,83,45,0.35)"
        _STAT_BORDER = "#166534"
        _STAT_LABEL = "#86efac"
        _STAT_VALUE = "#f0fdf4"
        _PHASE_COLOR = "#4ade80"
        _CYCLE_BG = "rgba(5,46,22,0.7)"
        _CYCLE_BORDER = "#15803d"
        _CYCLE_TITLE = "#bbf7d0"
        _CYCLE_SUB = "#6ee7b7"
        _FOOTER_BG = "rgba(17,24,39,0.6)"
        _FOOTER_BORDER = "#374151"
        _FOOTER_TEXT = "#9ca3af"
        _FOOTER_ACCENT = "#6ee7b7"
        _FOOTER_BOLD = "#d1fae5"
        _PULSE_CSS_BANNER = """
<style>
@keyframes pulse-border {
  0% { box-shadow: 0 0 0 0 rgba(22, 163, 74, 0.4); }
  70% { box-shadow: 0 0 0 10px rgba(22, 163, 74, 0); }
  100% { box-shadow: 0 0 0 0 rgba(22, 163, 74, 0); }
}
</style>
"""

    st.markdown(
        _PULSE_CSS_BANNER
        + f"""
<div style="
  background: {_BANNER_BG};
  border: 2px solid {_BANNER_BORDER};
  border-radius: 20px;
  padding: 44px 48px 36px;
  margin-bottom: 32px;
  box-shadow: {_BANNER_SHADOW};
  animation: pulse-border 2s infinite;
">

  <!-- Header -->
  <div style="display:flex;align-items:flex-start;gap:18px;margin-bottom:28px;">
    <div style="font-size:2.8rem;line-height:1;flex-shrink:0;">🛰️</div>
    <div>
      <div style="color:{_TITLE_COLOR};font-size:1.5rem;font-weight:800;letter-spacing:-0.02em;line-height:1.2;">
        Surveillance Job Running
      </div>
      <div style="color:{_SUBTITLE_COLOR};font-size:0.92rem;margin-top:6px;">
        Powered by AI surveillance engine · typically takes <b style="color:{_SUBTITLE_COLOR};">{_eta}</b>.
      </div>
    </div>
  </div>

  <!-- Stats grid -->
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:22px;">
    <div style="background:{_STAT_BG};border:1px solid {_STAT_BORDER};border-radius:12px;padding:18px 20px;">
      <div style="color:{_STAT_LABEL};font-size:0.72rem;text-transform:uppercase;letter-spacing:0.09em;margin-bottom:6px;">⏱ Job Running For</div>
      <div style="color:{_STAT_VALUE};font-size:1.75rem;font-weight:800;letter-spacing:-0.02em;">{_elapsed_str}</div>
    </div>
    <div style="background:{_STAT_BG};border:1px solid {_STAT_BORDER};border-radius:12px;padding:18px 20px;">
      <div style="color:{_STAT_LABEL};font-size:0.72rem;text-transform:uppercase;letter-spacing:0.09em;margin-bottom:6px;">⏳ Estimated Duration</div>
      <div style="color:{_STAT_VALUE};font-size:1.1rem;font-weight:700;">{_eta}</div>
    </div>
    <div style="background:{_STAT_BG};border:1px solid {_STAT_BORDER};border-radius:12px;padding:18px 20px;">
      <div style="color:{_STAT_LABEL};font-size:0.72rem;text-transform:uppercase;letter-spacing:0.09em;margin-bottom:6px;">📡 Current Phase</div>
      <div style="color:{_PHASE_COLOR};font-size:0.88rem;font-weight:600;line-height:1.4;">{_status_line}</div>
    </div>
  </div>

  <!-- Cycling activity message -->
  <div style="background:{_CYCLE_BG};border:1px solid {_CYCLE_BORDER};border-radius:12px;
              padding:18px 22px;margin-bottom:18px;display:flex;align-items:center;gap:14px;">
    <div style="font-size:1.7rem;flex-shrink:0;">{_cycle_icon}</div>
    <div>
      <div style="color:{_CYCLE_TITLE};font-size:1.0rem;font-weight:600;">{_cycle_msg}</div>
      <div style="color:{_CYCLE_SUB};font-size:0.78rem;margin-top:3px;">Processing step {_cycle_idx + 1} of {len(_CYCLE_MSGS)} · updates every 30 seconds</div>
    </div>
  </div>

  <!-- Info footer -->
  <div style="background:{_FOOTER_BG};border:1px solid {_FOOTER_BORDER};border-radius:10px;
              padding:14px 18px;color:{_FOOTER_TEXT};font-size:0.86rem;line-height:1.8;">
    <span style="color:{_FOOTER_ACCENT};">💡</span> <b style="color:{_FOOTER_BOLD};">{_close_note}</b><br>
    <span style="color:{_FOOTER_ACCENT};">🔄</span> This page auto-refreshes every 15 seconds — new results appear automatically when ready.<br>
    <span style="color:{_FOOTER_ACCENT};">🚫</span> The <b style="color:{_FOOTER_BOLD};">Run Flagship</b> button is locked until this job completes.
  </div>

</div>
""",
        unsafe_allow_html=True,
    )

    # Poll every 15 s while the job is still in flight so the UI stays
    # responsive.  (The fast-path above exits immediately on completion.)
    if _job_phase not in {"done", "complete", "error"}:
        _time.sleep(15)  # Polling interval — 15s reduces server blocking during long jobs
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
                _strip_pres = st.session_state.get("theme", "presentation") == "presentation"
                _strip_bg = "#FFFFFF" if _strip_pres else "#1f2937"
                _strip_border = "#E2E8F0" if _strip_pres else "#374151"
                _strip_text = "#4A5568" if _strip_pres else "#9ca3af"
                _strip_accent = "#0F766E" if _strip_pres else "#00D4C8"
                _strip_bold = "#1A202C" if _strip_pres else "#d1d5db"
                _strip_ts = "#1A202C" if _strip_pres else "#f9fafb"
                _strip_age = "#718096" if _strip_pres else "#6b7280"
                _strip_muted = "#A0AEC0" if _strip_pres else "#4b5563"
                st.markdown(
                    f'<div style="background:{_strip_bg};border:1px solid {_strip_border};border-radius:8px;'
                    f'padding:9px 16px;font-size:0.82rem;color:{_strip_text};line-height:1.7;">'
                    f'<span style="color:{_strip_accent};font-size:1rem;">📋</span>&nbsp;'
                    f'Showing <b style="color:{_strip_bold};">latest report</b> from '
                    f'<b style="color:{_strip_ts};">{_rpt_ts}</b>'
                    f'&nbsp;<span style="color:{_strip_age};">({_rpt_age_str})</span>'
                    f'&nbsp;·&nbsp;<span style="color:{_strip_muted};">'
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
                    f"**{_esc(c.get('company',''))}** — {_esc(c.get('biosimilar',''))} "
                    f"<span style='color:#9ca3af;font-size:0.82rem;'>({_esc(phase)})</span>{badge}",
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
                        f"🟢 **{_esc(c.get('company',''))}** · {_esc(c.get('biosimilar',''))}  \n"
                        f"<span style='color:#9ca3af;font-size:0.82rem;'>Markets: {_esc(c.get('countries','—'))}</span>",
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
            f'<div style="color:#9ca3af;font-size:0.70rem;margin-top:4px;">{_esc(_sub)}</div>'
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
                f'<div class="kpi-value" style="color:#f59e0b;font-size:1.3rem;">{_esc(top_name)}</div>'
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
            f'<div class="source">📌 {_esc(item.get("source",""))} &nbsp;·&nbsp; {_esc(item.get("date",""))}</div>'
            f'<div class="title">{_esc(item.get("title",""))}</div>'
            f'<div class="body">{_esc(item.get("summary",""))}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if not verified:
        st.info("No verified updates in this report.")


# ══════════════════════════════════════════════════════════════════════════════
# 2. PIPELINE TRACKER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🎯 Competitor Pipeline":
    st.title("🎯 Competitor Pipeline")

    if not companies:
        st.info("No pipeline data available yet. Run a new surveillance sweep to populate the tracker.")
        st.stop()

    df = pd.DataFrame(companies)

    # Ensure expected columns exist (new prompt schema may omit them)
    for _col in ("company", "biosimilar", "phase", "status", "countries",
                 "est_launch", "probability", "strengths_weaknesses", "source"):
        if _col not in df.columns:
            df[_col] = "" if _col != "probability" else 0

    # ── Quick-filter: Launched only toggle ───────────────────────────────────
    launched_only = st.toggle("✅ Show Launched only", value=False)

    # ── Filters row ──────────────────────────────────────────────────────────
    # Filter row — collapses gracefully on narrow screens
    fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 3], gap="small")
    company_filter = fc1.multiselect("Company",  sorted(df["company"].dropna().unique()))
    phase_filter   = fc2.multiselect("Phase",    sorted(df["phase"].dropna().unique()))
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
                '<span style="background:#065f46;color:#6ee7b7;padding:3px 10px;'
                'border-radius:99px;font-size:0.82rem;font-weight:700;">✅ Launched</span>'
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
            f'<td style="padding:10px 12px;font-weight:600;">{_esc(row.get("company",""))}</td>'
            f'<td style="padding:10px 12px;color:#a5b4fc;">{_esc(row.get("biosimilar",""))}</td>'
            f'<td style="padding:10px 12px;">{_phase_cell(_esc(str(row.get("phase",""))))}</td>'
            f'<td style="padding:10px 12px;color:#d1d5db;font-size:0.88rem;">{_esc(row.get("status",""))}</td>'
            f'<td style="padding:10px 12px;color:#9ca3af;">{_esc(row.get("countries",""))}</td>'
            f'<td style="padding:10px 12px;">{_esc(row.get("est_launch",""))}</td>'
            f'<td style="padding:10px 12px;">{_prob_cell(int(row.get("probability", 0)))}</td>'
            f'<td style="padding:10px 12px;color:#9ca3af;font-size:0.85rem;">{_esc(row.get("strengths_weaknesses",""))}</td>'
            f'</tr>'
        )

    _tbl_pres = st.session_state.get("theme", "presentation") == "presentation"
    _tbl_bg = "#FFFFFF" if _tbl_pres else "#1f2937"
    _tbl_border = "#E2E8F0" if _tbl_pres else "#374151"
    _tbl_hd_bg = "#F7FAFC" if _tbl_pres else "#111827"
    _tbl_hd_border = "#E2E8F0" if _tbl_pres else "#374151"
    _tbl_text = "#1A202C" if _tbl_pres else "#f3f4f6"
    _tbl_th = "#4A5568" if _tbl_pres else "#9ca3af"
    html_table = f"""
    <div style="overflow-x:auto;border-radius:10px;border:1px solid {_tbl_border};">
    <table style="width:100%;border-collapse:collapse;background:{_tbl_bg};color:{_tbl_text};font-size:0.9rem;">
      <thead>
        <tr style="background:{_tbl_hd_bg};border-bottom:2px solid {_tbl_hd_border};">
          <th style="padding:12px;text-align:left;color:{_tbl_th};">Company</th>
          <th style="padding:12px;text-align:left;color:{_tbl_th};">Biosimilar</th>
          <th style="padding:12px;text-align:left;color:{_tbl_th};">Phase</th>
          <th style="padding:12px;text-align:left;color:{_tbl_th};">Status</th>
          <th style="padding:12px;text-align:left;color:{_tbl_th};">Countries</th>
          <th style="padding:12px;text-align:left;color:{_tbl_th};">Est. Launch</th>
          <th style="padding:12px;text-align:left;color:{_tbl_th};">Probability</th>
          <th style="padding:12px;text-align:left;color:{_tbl_th};">Notes</th>
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
        template=_PLOTLY_TEMPLATE,
    )
    fig.update_layout(
        paper_bgcolor=_PLOTLY_PAPER_BG,
        plot_bgcolor=_PLOTLY_PLOT_BG,
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
                    f'<a class="post-link" href="{_esc(_post_url)}" target="_blank" rel="noopener noreferrer">'
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
                f'<span class="platform-badge">🌐 {_esc(_platform)}</span>'
                f'<span class="user">{_esc(post.get("user","@unknown"))}</span>'
                f'<span class="time">{_esc(post.get("date",""))}</span>'
                f'{sentiment_badge(_esc(post.get("sentiment","Neutral")))}'
                f'</div>'
                f'{_link_html}'
                f'</div>'
                f'<div class="text">{_esc(post.get("post",""))}</div>'
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
            paper_bgcolor=_PLOTLY_PAPER_BG,
            font_color=_PLOTLY_FONT_COLOR,
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
                template=_PLOTLY_TEMPLATE,
                paper_bgcolor=_PLOTLY_PAPER_BG,
                plot_bgcolor=_PLOTLY_PLOT_BG,
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
        st.info("No pipeline data available yet. Run a new surveillance sweep to populate the timeline.")
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
            "Company":    c.get("company", "Unknown"),
            "Biosimilar": c.get("biosimilar", ""),
            "Phase":      phase,
            "Start":      start_dt,
            "Finish":     end_dt,
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
        template=_PLOTLY_TEMPLATE,
        title="Estimated Phase Timeline (next 24 months)",
    )
    fig_gantt.update_yaxes(autorange="reversed")
    fig_gantt.update_layout(
        paper_bgcolor=_PLOTLY_PAPER_BG,
        plot_bgcolor=_PLOTLY_PLOT_BG,
        font_color=_PLOTLY_FONT_COLOR,
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
        today = _date.today()
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
                            _threat_pres = st.session_state.get("theme", "presentation") == "presentation"
                            _threat_bg = "#FFFFFF" if _threat_pres else "#1f2937"
                            _threat_text = "#1A202C" if _threat_pres else "#f3f4f6"
                            _threat_sub = "#4A5568" if _threat_pres else "#94a3b8"
                            _threat_muted = "#718096" if _threat_pres else "#cbd5e1"
                            _threat_border = "#E2E8F0" if _threat_pres else "#374151"
                            st.markdown(
                                f'<div style="background:{_threat_bg};border:1px solid {rs["bg"]};'
                                f'border-top:3px solid {rs["bg"]};border-radius:8px;'
                                f'padding:12px 14px;margin-bottom:10px;">'
                                f'<div style="display:flex;justify-content:space-between;'
                                f'align-items:center;margin-bottom:8px;">'
                                f'<span style="font-weight:700;font-size:0.95rem;'
                                f'color:{_threat_text};">📍 {country}</span>'
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
                                    "#DC2626" if "Imminent" in ttt or "Already" in ttt
                                    else "#D97706" if "months" in ttt
                                    else "#718096" if _threat_pres else "#9ca3af"
                                )
                                acts_html = "".join(
                                    f'<li style="margin:2px 0;">{a}</li>' for a in acts
                                )
                                st.markdown(
                                    f'<div style="border-top:1px solid {_threat_border};'
                                    f'padding-top:8px;margin-top:6px;">'
                                    f'<div style="font-weight:600;color:{_threat_text};'
                                    f'font-size:0.85rem;">{_esc(t.get("company",""))}</div>'
                                    f'<div style="color:{_threat_sub};font-size:0.78rem;'
                                    f'margin-bottom:4px;">{_esc(t.get("biosimilar",""))} &nbsp;·&nbsp; {_esc(phase)}</div>'
                                    f'<div style="color:{ttt_color};font-size:0.78rem;'
                                    f'font-weight:600;margin-bottom:6px;">⏱ {_esc(ttt)}</div>'
                                    f'<div style="color:{_threat_muted};font-size:0.75rem;">'
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
                f"**📍 {_esc(t.get('country',''))}** ({_esc(t.get('region',''))} · "
                f"{_esc(t.get('operational_model',''))})\n\n"
                f"> **Competitor:** {_esc(t.get('company',''))} &nbsp;·&nbsp; "
                f"**Biosimilar:** {_esc(t.get('biosimilar',''))} &nbsp;·&nbsp; "
                f"**Phase:** {_esc(t.get('phase',''))} &nbsp;·&nbsp; "
                f"**Est. Launch:** {_esc(t.get('est_launch','TBD'))}\n\n"
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
    _model_counts: dict[str, int] = {}
    for r in all_reports:
        mv = r.get("model_version") or MODEL_FAST
        tag = _model_tag(mv)
        _model_counts[tag] = _model_counts.get(tag, 0) + 1
    _c1, _c2 = st.columns(2)
    _c1.metric("📊 Total Reports", len(all_reports))
    with _c2:
        st.markdown("**Models used**")
        for tag, count in sorted(_model_counts.items()):
            st.caption(f"• {tag}: {count}")
    st.caption("Click **Load** to view any historical report on the Dashboard for side-by-side comparison.")
    st.markdown("---")

    for rep in all_reports:
        ts = rep.get("run_date", "")[:19].replace("T", " ")
        summary = rep.get("summary", "No summary") or "No summary"
        mv = rep.get("model_version") or MODEL_FAST
        _badge_html, _border_color = _model_badge(mv)
        _tag = _model_tag(mv)

        col_exp, col_btn = st.columns([9, 1])
        with col_exp:
            with st.expander(f"📄 Report #{rep['id']}  —  {ts}  —  {_tag}"):
                st.markdown(_badge_html, unsafe_allow_html=True)
                st.caption(f"Model: `{mv}`")
                st.write(summary[:600] + ("…" if len(summary) > 600 else ""))
        with col_btn:
            if st.button("Load", key=f"_load_{rep['id']}", use_container_width=True, help="Load this report onto the Dashboard"):
                st.session_state["_load_report_id"] = rep["id"]
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# 9. MODEL LAB
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🧪 Model Lab":
    st.title("🧪 Model Comparison Lab")
    st.caption("Compare how different AI models analyzed the same surveillance date")

    # ── Helpers ──
    _SLUG_TO_DISPLAY = {v: k for k, v in _MODEL_OPTIONS.items()}

    def _get_model_name(model_slug: str | None) -> str:
        if not model_slug:
            return "Legacy Report"
        return _SLUG_TO_DISPLAY.get(model_slug, model_slug.split("/")[-1].replace("-", " ").title())

    def _extract_companies(raw: dict) -> list:
        """Handle both old schema (companies) and clinical-rewrite schema (pipeline_tracker)."""
        if "companies" in raw and raw["companies"]:
            return raw["companies"]
        if "pipeline_tracker" in raw and raw["pipeline_tracker"]:
            return raw["pipeline_tracker"]
        return []

    def _extract_summary(raw: dict) -> str:
        return raw.get("executive_summary", "") or raw.get("ai_insights", "") or "No summary generated"

    def _extract_verified(raw: dict) -> list:
        return raw.get("verified_updates", []) or []

    def _extract_threats(raw: dict) -> list:
        return raw.get("my_markets_threat", []) or []

    # Get all reports with model_version
    _all = get_all_reports()
    _dated = {}
    for r in _all:
        _d = r.get("run_date", "")[:10]
        _m = r.get("model_version") or "Legacy"
        if _d not in _dated:
            _dated[_d] = {}
        _dated[_d][_m] = r

    _dates = sorted(_dated.keys(), reverse=True)

    if not _dates:
        st.info("No reports found. Run surveillance with different models to enable comparison.")
    else:
        _sel_date = st.selectbox("Select Run Date", _dates)
        _reports = _dated[_sel_date]

        st.markdown(f"### Reports for {_sel_date}")
        st.caption(f"Found {len(_reports)} model(s) for this date")

        # ── COMPANY FINDINGS COMPARISON ──
        st.markdown("---")
        st.subheader("🏢 Who Found Which Competitors?")

        _companies_found = {}
        for model, report in _reports.items():
            raw = json.loads(report.get("raw_json", "{}"))
            _comps = _extract_companies(raw)
            _companies_found[_get_model_name(model)] = {
                "count": len(_comps),
                "launched": [c.get("company", "Unknown") for c in _comps if c.get("phase") == "Launched"],
                "phase3": [c.get("company", "Unknown") for c in _comps if c.get("phase") == "Phase III"],
                "approved": [c.get("company", "Unknown") for c in _comps if c.get("phase") == "Approved"],
            }

        _st = st.container()
        for _model_name, _data in _companies_found.items():
            with _st.expander(f"{_model_name} — {_data['count']} companies found"):
                if _data["launched"]:
                    st.markdown(f"🚀 **Launched:** {', '.join(_data['launched'])}")
                if _data["approved"]:
                    st.markdown(f"✅ **Approved:** {', '.join(_data['approved'])}")
                if _data["phase3"]:
                    st.markdown(f"🔬 **Phase III:** {', '.join(_data['phase3'])}")
                if not any([_data["launched"], _data["approved"], _data["phase3"]]):
                    st.caption("No advanced-phase competitors detected")

        # ── THREAT LANDSCAPE COMPARISON ──
        st.markdown("---")
        st.subheader("🌍 Threat Landscape by Model")

        _threat_data = {}
        for model, report in _reports.items():
            raw = json.loads(report.get("raw_json", "{}"))
            _threats = _extract_threats(raw)
            _model_name = _get_model_name(model)
            _threat_data[_model_name] = {
                "high": [t.get("country", "Unknown") for t in _threats if t.get("risk_level") == "High"],
                "medium": [t.get("country", "Unknown") for t in _threats if t.get("risk_level") == "Medium"],
                "launched_countries": [t.get("country", "Unknown") for t in _threats if t.get("phase") == "Launched"],
            }

        _threat_cols = st.columns(len(_threat_data))
        for i, (_model_name, _t) in enumerate(_threat_data.items()):
            with _threat_cols[i]:
                st.markdown(f"**{_model_name}**")
                st.metric("High Risk", len(_t["high"]))
                st.metric("Medium Risk", len(_t["medium"]))
                if _t["launched_countries"]:
                    st.caption(f"🚀 Launched in: {', '.join(_t['launched_countries'][:3])}")

        # ── EXECUTIVE SUMMARY SHOWDOWN ──
        st.markdown("---")
        st.subheader("🥊 Executive Summary Showdown")

        _valid_summaries = {}
        for model, report in _reports.items():
            raw = json.loads(report.get("raw_json", "{}"))
            _summ = _extract_summary(raw)
            if _summ and _summ != "No summary generated":
                _valid_summaries[_get_model_name(model)] = _summ

        if _valid_summaries:
            _sum_cols = st.columns(len(_valid_summaries))
            for i, (model_name, summary) in enumerate(_valid_summaries.items()):
                with _sum_cols[i]:
                    st.markdown(f"**{model_name}**")
                    st.info(summary[:300])
                    if len(summary) > 300:
                        with st.expander("Read full summary"):
                            st.write(summary)
        else:
            st.warning("No executive summaries found for comparison. Run surveillance with multiple models on the same date.")

        # ── RECOMMENDATIONS SHOWDOWN ──
        st.markdown("---")
        st.subheader("🎯 Recommended Actions Comparison")

        _recs = {}
        for model, report in _reports.items():
            raw = json.loads(report.get("raw_json", "{}"))
            _model_name = _get_model_name(model)
            _all_recs = []
            for t in raw.get("my_markets_threat", []):
                _all_recs.extend(t.get("recommended_actions", []))
            _recs[_model_name] = list(dict.fromkeys(_all_recs))[:5]

        for _model_name, _actions in _recs.items():
            with st.expander(f"{_model_name} — Top Recommendations"):
                for _a in _actions:
                    st.markdown(f"- {_a}")
                if not _actions:
                    st.caption("No specific recommendations generated")

        # ── URL VERIFICATION COMPARISON ──
        st.markdown("---")
        st.subheader("🔗 URL Quality Comparison")

        _url_data = {}
        for model, report in _reports.items():
            raw = json.loads(report.get("raw_json", "{}"))
            _updates = _extract_verified(raw)
            _verified = [u for u in _updates if u.get("url") and u.get("url_verified")]
            _model_name = _get_model_name(model)
            _url_data[_model_name] = {
                "total": len(_updates),
                "verified": len(_verified),
                "sources": list(set(u.get("source", "Unknown") for u in _updates))[:5],
            }

        _url_cols = st.columns(len(_url_data))
        for i, (_model_name, _u) in enumerate(_url_data.items()):
            with _url_cols[i]:
                st.markdown(f"**{_model_name}**")
                if _u["total"] > 0:
                    _pct = round(_u["verified"] / _u["total"] * 100, 1)
                    st.metric("Verified URLs", f"{_u['verified']}/{_u['total']}", f"{_pct}%")
                else:
                    st.metric("Verified URLs", "0/0")
                if _u["sources"]:
                    st.caption(f"Sources: {', '.join(_u['sources'])}")

        # ── WINNER BADGE ──
        st.markdown("---")
        _winner_score = {}
        for _model_name in _companies_found.keys():
            _c_score = _companies_found[_model_name]["count"]
            _t_score = len(_threat_data.get(_model_name, {}).get("high", []))
            _u_score = _url_data.get(_model_name, {}).get("verified", 0)
            _winner_score[_model_name] = _c_score * 2 + _t_score * 3 + _u_score

        if _winner_score:
            _winner_name = max(_winner_score, key=_winner_score.get)
            _winner_points = _winner_score[_winner_name]
            st.success(
                f"🏆 Winner for {_sel_date}: **{_winner_name}** "
                f"(Score: {_winner_points} — based on companies found ×2 + high-risk markets ×3 + verified URLs)"
            )
        else:
            st.info("Run surveillance with multiple models to generate a winner comparison.")

        # ── COST COMPARISON ──
        st.markdown("---")
        st.subheader("💰 Cost Comparison")
        _cost_map = {
            "grok-4.20-reasoning": "$0.00 (xAI direct)",
            "anthropic/claude-sonnet-4.5": "~$0.45",
            "google/gemini-2.5-pro-preview-03-25": "~$0.30",
            "deepseek/deepseek-v4-pro": "~$0.08",
        }
        for model in _reports.keys():
            _friendly = _get_model_name(model)
            st.caption(f"{_friendly}: {_cost_map.get(model, 'N/A')}")
