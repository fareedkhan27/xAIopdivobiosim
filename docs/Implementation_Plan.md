# Opdivo (Nivolumab) Biosimilar Surveillance Tool  
**Complete End-to-End Implementation Plan**

**Project Goal**  
Build a live, automated dashboard that monitors all biosimilar activity for Opdivo (nivolumab) across clinical trials, regulatory filings (FDA, EMA, PMDA, CDSCO, etc.), launches, rejections, and social noise on X (Twitter).  
Separate **Verified Intelligence** from **Social Noise**. Use Grok API Batch mode for 50% cost savings. Fully automated weekly updates with email alerts.

**Key Features**
- Real-time web + X search via Grok tools
- Structured JSON output from Grok
- Pipeline Tracker table
- Verified Intelligence feed
- Social Noise with sentiment
- AI Insights + executive summary
- Gantt-style Timeline
- Automatic weekly Batch job (50% cheaper)
- Email alert when new report is ready
- Streamlit dashboard (matches provided wireframes)
- SQLite storage for history

## Tech Stack
- **Backend**: Python 3.11+
- **Dashboard**: Streamlit
- **AI/API**: xAI Grok API (grok-4-1-fast-reasoning + Batch API)
- **Database**: SQLite
- **Scheduler**: APScheduler
- **Notifications**: SMTP (Gmail)
- **Deployment**: Render.com or Railway.app (free tier)

## Project Folder Structure

opdivo-surveillance/ ├── .env ├── requirements.txt ├── README.md ├── db.py ├── prompts.py ├── agent.py ├── scheduler.py ├── notifications.py ├── main.py └── opdivo_reports.db # auto-created

text

````
## Prerequisites
1. xAI API key from https://console.x.ai (X Premium required)
2. Gmail account + App Password for email alerts
3. Python 3.11+ installed

## Phase-by-Phase Implementation Plan

### Phase 0: Setup (1 day)
- Create project folder
- Install dependencies (`pip install -r requirements.txt`)
- Create `.env` with `XAI_API_KEY`, email credentials
- Run `python -c "from db import init_db; init_db()"`

### Phase 1: Core Backend & Structured Grok Calls (2 days)
- Implement `prompts.py` (structured JSON prompt)
- Implement `db.py`
- Implement `agent.py` (Batch + structured JSON + polling)

### Phase 2: Scheduler & Automation (1 day)
- Implement `scheduler.py` (weekly Sunday 3 AM Batch job)

### Phase 3: Notifications (1 day)
- Implement `notifications.py`
- Integrate email into `agent.py`

### Phase 4: Full Dashboard (3–4 days)
- Implement `main.py` with all 6 tabs using live parsed JSON
- Match the exact wireframes provided earlier

### Phase 5: Testing (2 days)
- Run manual Batch job
- Verify JSON parsing in every tab
- Test email alerts
- Test scheduler

### Phase 6: Deployment & Go-Live (1–2 days)
- Deploy on Render.com (Web Service for Streamlit + Background Worker for scheduler)
- Set environment variables
- Buy domain (optional)
- Go live

## Full Code Files

### 1. `requirements.txt`
```txt
streamlit
xai-sdk
pandas
python-dotenv
apscheduler
````

### 2. .env (example)

env

`XAI_API_KEY=sk-... EMAIL_SENDER=your.email@gmail.com EMAIL_PASSWORD=your_app_password EMAIL_RECIPIENT=your.email@gmail.com SMTP_SERVER=smtp.gmail.com SMTP_PORT=587`

### 3. db.py

Python

```
import sqlite3
import json
from datetime import datetime

def get_db():
    conn = sqlite3.connect("opdivo_reports.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY,
            run_date TEXT,
            raw_json TEXT,
            summary TEXT
        );
    """)
    conn.commit()
    conn.close()

def save_report(raw_json, summary):
    conn = get_db()
    conn.execute("INSERT INTO reports (run_date, raw_json, summary) VALUES (?, ?, ?)",
                 (datetime.now().isoformat(), json.dumps(raw_json), summary))
    conn.commit()
    conn.close()

def get_latest_report():
    conn = get_db()
    row = conn.execute("SELECT * FROM reports ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None
```

### 4. prompts.py

Python

```
OPDIVO_SURVEILLANCE_PROMPT = """
You are an expert Biosimilar Surveillance Agent for Opdivo (nivolumab) by BMS.

Companies to monitor: Zydus, Amgen (ABP 206), Sandoz, Boan Biotech, Henlius (HLX18), Reliance, Xbrane/Intas, Biocon, and any new entrants.

Return ONLY a valid JSON object with this exact structure:

{
  "executive_summary": "Short 2-3 sentence overview with key alerts",
  "companies": [ { "company": "...", "biosimilar": "...", "phase": "...", "status": "...", "countries": "...", "est_launch": "...", "probability": 95, "strengths_weaknesses": "..." } ],
  "verified_updates": [ { "source": "...", "date": "2026-04-25", "title": "...", "summary": "..." } ],
  "social_noise": [ { "user": "@...", "time": "2h ago", "post": "...", "sentiment": "Positive/Neutral/Negative" } ],
  "ai_insights": "Grok's deeper reasoning"
}

Use web_search, x_search, browse_page tools as needed. Be factual and up-to-date.
"""
```

### 5–8. Remaining Files (agent.py, scheduler.py, notifications.py, main.py)

Use the **exact final versions** I provided in the previous messages (structured JSON version with email + live parsing in all tabs).

## Deployment Instructions (Render.com)

1. Push code to GitHub
2. Create two services on Render:
    - Web Service → main.py (Streamlit)
    - Background Worker → scheduler.py
3. Add all .env variables
4. Done!

**Total Estimated Effort**: 2–4 weeks for a solo developer (or 1 week with a small team).

**Cost (first year)**: <$100 (mostly one-time hosting + tiny Grok Batch usage).

You now have everything needed to hand this off and get the full tool built exactly as specified.