# AGENTS.md — Opdivo Biosimilar Surveillance Tool

> This file is for AI coding agents. It describes the project architecture, conventions, and critical safety rules.

---

## Project Overview

This is a **fully automated competitive-intelligence dashboard** that monitors biosimilar development for **Opdivo (nivolumab)** in real time. It is built for the Bristol Myers Squibb (BMS) Global Oncology Operations team, with a specific focus on LR (Low-Resource) priority markets across CEE/EU, LATAM, and MEA.

The system uses the **xAI Grok API** (via the official `xai-sdk`) to perform structured web + X (Twitter) searches, then stores results in **SQLite** and surfaces them through a **Streamlit** dashboard. A weekly **APScheduler** job keeps the data fresh automatically. Email alerts are sent when reports are ready or when high-risk threats are detected.

Key features:
- Real-time web + X search via Grok tools
- Clear separation between **Verified Intelligence** and **Social Noise**
- Pipeline tracker with launch-probability scores
- LR Markets threat monitor with per-country risk cards and recommended actions
- Automatic weekly Batch-mode surveillance (~$0.05/run, 50% cheaper than sync)
- Email alerts via Resend API (primary) or Gmail SMTP (fallback)
- Dark-mode, mobile-first Streamlit dashboard

---

## Technology Stack

| Component     | Technology / Package              |
|---------------|-----------------------------------|
| Language      | Python 3.11+                      |
| Dashboard     | Streamlit >= 1.32.0               |
| AI / Search   | xAI Grok API (`xai-sdk >= 0.1.0`) |
| Database      | SQLite (`sqlite3` stdlib)         |
| Scheduler     | APScheduler >= 3.10.0             |
| Charts        | Plotly >= 5.20.0, pandas >= 2.0.0 |
| Email         | Resend API (`resend >= 2.0.0`)    |
| Env config    | `python-dotenv >= 1.0.0`          |

---

## Project Structure

```
opdivo-surveillance/
├── .env                     # Secrets — NEVER committed (see .env.example)
├── .env.example             # Template for required env vars
├── requirements.txt         # Python dependencies
├── main.py                  # Streamlit dashboard (~2000 lines, all UI + routing)
├── agent.py                 # Grok API client, batch orchestration, JSON parser
├── db.py                    # SQLite persistence layer (append-only, WAL mode)
├── prompts.py               # Single structured JSON prompt for Grok
├── notifications.py         # Email alerts (Resend primary, SMTP fallback)
├── scheduler.py             # APScheduler weekly job wrapper
├── test_api.py              # Standalone xAI API connectivity test
├── opdivo_reports.db        # Auto-created SQLite database
├── docs/
│   ├── README.md            # Human-facing quick-start guide
│   ├── Implementation_Plan.md
│   └── Wireframes_UI_SPEC.md
└── wireframes/              # Reference images (ignored by git)
```

### Module Responsibilities

- **`main.py`** — Streamlit entry point. Handles:
  - Password gate (`_CORRECT_PASSWORD = "1001"`)
  - Session-state bootstrap and job-progress reconciliation
  - Sidebar navigation and "Run Now" / "Run Flagship" buttons
  - All dashboard pages: Dashboard, Pipeline Tracker, Verified Intelligence, Social Noise, AI Insights, Timeline, LR Markets, History
  - Extensive dark-mode CSS (mobile-first, responsive breakpoints)

- **`agent.py`** — Core AI orchestration:
  - `submit_batch_job()` / `poll_batch_job()` — Batch API (50% cost savings)
  - `_call_chat()` — Synchronous fallback
  - `parse_grok_response()` — Strips markdown fences, parses JSON, normalises schema, patches known ground-truth entries (e.g. Zydus Tishtha launched in India)
  - `run_surveillance()` — Full pipeline: submit/poll → parse → save → email
  - Thread-safe `JOB_STATUS` dict shared with the Streamlit UI

- **`db.py`** — Data-safety-critical SQLite layer:
  - `init_db()` — `CREATE TABLE IF NOT EXISTS` only; never drops data
  - `save_report()` — Append-only INSERT
  - `get_latest_report()`, `get_all_reports()`, `get_report_by_id()` — Read-only
  - WAL journal mode (`PRAGMA journal_mode=WAL`) for concurrent reads/writes
  - `_safe_add_column()` — Only approved schema-migration path
  - `DB_PATH` overridable via environment variable for persistent Volume mounts

- **`prompts.py`** — Single string constant `OPDIVO_SURVEILLANCE_PROMPT`.
  - Defines strict JSON output schema with required fields:
    `report_date`, `executive_summary`, `companies`, `verified_updates`, `social_noise`, `my_markets_threat`, `ai_insights`
  - Lists all monitored companies and all LR priority markets
  - Includes hard rules (no trailing commas, no hallucinated URLs, `probability` 0–100, etc.)

- **`notifications.py`** — Email transport:
  - Primary: Resend HTTP API (port 443, works on Railway)
  - Fallback: Gmail SMTP_SSL / STARTTLS (local dev only)
  - `send_report_ready_email()` — Standard report alert with KPI summary
  - `send_high_risk_alert()` — Priority alert when `risk_level == "High"`
  - `send_test_email()` — Synthetic test to verify template rendering

- **`scheduler.py`** — Minimal APScheduler wrapper:
  - Runs `agent.run_surveillance(use_batch=True)` every Sunday at 03:00 AM ET
  - Blocking scheduler; start with `python scheduler.py`

---

## Build and Run Commands

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env and fill in real values (XAI_API_KEY is mandatory)
```

### 3. Initialise database
```bash
python -c "from db import init_db; init_db()"
```

### 4. Run the dashboard
```bash
streamlit run main.py
```
Open the URL shown (usually `http://localhost:8501`).

### 5. Run the scheduler (in a second terminal)
```bash
python scheduler.py
```

### 6. Test API connectivity
```bash
python test_api.py
```

### 7. Run a one-off surveillance job from CLI
```bash
python agent.py           # Batch mode (default)
python agent.py --sync    # Synchronous mode (faster, more expensive)
```

---

## Environment Variables

| Variable          | Required? | Purpose                                      |
|-------------------|-----------|----------------------------------------------|
| `XAI_API_KEY`     | **Yes**   | xAI Grok API key                             |
| `ACCESS_CODE`     | No        | Dashboard login code (default: `1001`)       |
| `FLAGSHIP_CODE`   | No        | Flagship run access code (default: `flagship2026`) |
| `RESEND_API_KEY`  | No        | Resend API key (production email)            |
| `EMAIL_SENDER`    | No*       | From address (must be verified in Resend)    |
| `EMAIL_RECIPIENT` | No*       | Destination address for alerts               |
| `EMAIL_PASSWORD`  | No*       | Gmail app password (SMTP fallback only)      |
| `SMTP_SERVER`     | No        | Default: `smtp.gmail.com`                    |
| `SMTP_PORT`       | No        | Default: `465`                               |
| `DB_PATH`         | No        | Override SQLite file path (e.g. for Railway Volume) |

\* Required if you want email alerts. For local dev without Resend, Gmail SMTP fallback works if `EMAIL_PASSWORD` is set.

---

## Code Style Guidelines

- **Language**: All comments, docstrings, and user-facing UI text are in **English**.
- **Type hints**: Used in `db.py` and `agent.py` for public function signatures.
- **String formatting**: Mix of f-strings and `.format()`; follow existing convention in the file you edit.
- **CSS**: Inline styles via `st.markdown(..., unsafe_allow_html=True)`. Custom classes (`.kpi-card`, `.post-card`, etc.) live in a large `<style>` block near the top of `main.py`.
- **Constants**: UPPER_SNAKE_CASE for module-level constants (e.g. `BATCH_TIMEOUT`, `MODEL_FAST`).
- **Logging**: Standard `logging` module with consistent format:
  ```python
  format="%(asctime)s [agent] %(levelname)s %(message)s"
  ```

---

## Testing Instructions

There is **no automated test suite** (no `pytest`, no `unittest`). All testing is manual:

1. **API test**: `python test_api.py` — verifies xAI API key and basic chat completion.
2. **DB test**: `python -c "from db import init_db, get_report_count; init_db(); print(get_report_count())"`
3. **Email test**: Click **"🧪 Send Test Email"** in the Streamlit sidebar, or run:
   ```python
   from notifications import send_test_email
   send_test_email()
   ```
4. **Surveillance test**: Click **"▶ Run Now"** in the Streamlit sidebar (Batch mode, ~15–90 min) or run `python agent.py --sync` (~5–20 min).
5. **Scheduler test**: Temporarily change the CronTrigger in `scheduler.py` to a near-future time, start `python scheduler.py`, and verify execution.

After any code change, restart the Streamlit server (`Ctrl+C` then `streamlit run main.py`) because Streamlit caches imports aggressively.

---

## Security Considerations

- **NEVER commit `.env`** — it is listed in `.gitignore`.
- **API key handling**: `agent.py` loads the key via `os.getenv`, raises `EnvironmentError` early if missing, and immediately deletes the local variable (`del _api_key`) so it does not persist as a module attribute.
- **Password gate**: The Streamlit dashboard is protected by an access code read from the `ACCESS_CODE` environment variable (falls back to `1001`). This is **not** a robust auth system — it is a simple stopgap. Do not rely on it for sensitive data exposure without additional layers.
- **XSS prevention**: All Grok-generated strings rendered via `unsafe_allow_html=True` are passed through `html.escape()` before injection into HTML templates.
- **URL trust**: Social-media URLs from Grok are only rendered as clickable links when `url_verified` is `True`. Unverified URLs are shown as plain text or stripped entirely (`parse_grok_response` enforces this).
- **SQL injection safety**: `db.py` uses parameterized queries exclusively (`?` placeholders). No raw string interpolation into SQL.
- **Email transport**: Resend API (HTTPS/443) is preferred over SMTP because cloud hosts (Railway, Render) often block SMTP ports.

---

## Deployment

**Recommended platform**: [Render.com](https://render.com)

1. Push code to GitHub.
2. Create a **Web Service** → `main.py` (Streamlit)
3. Create a **Background Worker** → `scheduler.py`
4. Add all environment variables from `.env`
5. Deploy

**Railway.app note**: Mount a **persistent Volume** at the `DB_PATH` location (e.g. `/data/opdivo_reports.db`) so the SQLite file survives redeploys. Without a Volume the database resets on every deploy.

---

## Critical Data-Safety Rules

The database is designed to preserve **all historical reports forever**.

- Every surveillance run **appends** a new row — old rows are **never deleted**.
- `init_db()` uses `CREATE TABLE IF NOT EXISTS` — it **never drops or recreates** tables.
- Schema migrations **must** use `_safe_add_column()` (`ALTER TABLE … ADD COLUMN`) — never `DROP COLUMN`, never recreate the table.
- There are **no `DELETE`, `DROP TABLE`, or `TRUNCATE`** statements anywhere in the codebase.

If you modify `db.py`, re-read the top-of-file docstring before making any schema change.

---

## Key Architectural Patterns

### Threading model
- The Streamlit main script runs on a single thread. Surveillance jobs run in a **background `threading.Thread`** (`run_surveillance_thread` in `main.py`).
- **Never mutate Streamlit session state** inside the worker thread. The main script reconciles completion by polling `agent.JOB_STATUS` (a thread-safe dict protected by `_JOB_STATUS_LOCK`).

### Session-state caching
- `st.session_state["last_report"]` caches the latest DB row to avoid redundant queries on every Streamlit rerun.
- The cache is invalidated in two places only:
  1. Immediately after a job completes (`reconcile_job_state_from_agent()`)
  2. On the very first load of a new session

### Batch vs Sync
- **Batch mode** (default): Cheaper, slower (15–90 min). Uses `client.batch.create()` → `add()` → poll.
- **Sync mode**: More expensive, faster (5–20 min). Uses `client.chat.create()` → `chat.sample()`.
- The scheduler always uses Batch. The dashboard sidebar lets the user choose.

### Grok response parsing
- `parse_grok_response()` strips markdown fences, runs `json.loads()`, normalises fields for backwards compatibility, and patches known ground-truth entries (e.g. ensuring Zydus is marked "Launched" even if the model omits it).
- The prompt in `prompts.py` demands strict JSON with no trailing commas.

---

## Files to Read Before Making Changes

| If you want to change … | Read these files first |
|--------------------------|------------------------|
| Dashboard UI / layout    | `main.py` (top CSS block + page routing sections) |
| Prompt / JSON schema     | `prompts.py` |
| AI orchestration / batch | `agent.py` (submit, poll, parse, run_surveillance) |
| Database schema / queries| `db.py` (read the DATA-SAFETY header) |
| Email templates          | `notifications.py` (HTML is inline) |
| Scheduling logic         | `scheduler.py` |

---

## Contact / Ownership

This is a single-maintainer biopharma competitive-intelligence tool. There is no formal CI/CD, no PR process, and no issue tracker. Changes are deployed manually by pushing to the hosting platform.
