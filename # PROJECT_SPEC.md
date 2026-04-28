# PROJECT_SPEC.md
**Opdivo (Nivolumab) Biosimilar Surveillance Tool - Full Project Specification**

## 1. Project Overview
Build a fully automated, professional dashboard that monitors biosimilar development for **Opdivo (nivolumab)** by BMS.

It tracks:
- Clinical trials and phases
- Regulatory filings and approvals (FDA, EMA, PMDA, CDSCO, etc.)
- Launches, rejections, and country entry plans
- Social noise on X (Twitter)

**Core Requirement**: Separate **Verified Intelligence** (official sources) from **Social Noise**.

Use **Grok API Batch mode** (50% cost savings) for weekly automated runs.

## 2. Key Features
- Automatic weekly surveillance using Grok Batch API
- Structured JSON output from Grok
- Dark-mode Streamlit dashboard
- Pipeline Tracker table with probability scoring
- Verified Intelligence feed
- Social Noise with sentiment analysis
- AI Insights + Executive Summary
- Competitive Timeline (Gantt-style)
- Email alerts when new report is ready
- Export to CSV
- Extremely low cost (~$0.05 per weekly run)

## 3. Tech Stack
- Python 3.11+
- Streamlit (dashboard)
- xAI Grok API (grok-4-1-fast-reasoning + Batch mode + tools)
- SQLite (database)
- APScheduler (weekly automation)
- SMTP (email alerts)

## 4. Folder Structure
opdivo-surveillance/
├── .env
├── requirements.txt
├── db.py
├── prompts.py
├── agent.py
├── scheduler.py
├── notifications.py
├── main.py
├── opdivo_reports.db          # auto-created
├── README.md
├── IMPLEMENTATION_PLAN.md
└── WIREFRAMES_UI_SPEC.md
text## 5. Wireframes & UI Specification (Dark Mode)
**Navigation Sidebar** (fixed left):
- Dashboard
- Pipeline Tracker
- Verified Intelligence
- Social Noise
- AI Insights
- Timeline

**Dashboard**: KPI cards, latest verified updates, quick AI insights.

**Pipeline Tracker**: Sortable table (Company, Biosimilar, Phase, Status, Countries, Est. Launch, Probability bar).

**Verified Intelligence**: Expandable cards with source, date, title, summary.

**Social Noise**: Left = X post feed with sentiment; Right = sentiment chart + keywords.

**AI Insights**: Executive summary, risk heatmap, Grok’s reasoning.

**Timeline**: Horizontal Gantt chart (next 24 months).

## 6. Grok JSON Output Structure (MUST follow exactly)
```json
{
  "executive_summary": "Short overview with key alerts",
  "companies": [
    {
      "company": "Zydus Lifesciences",
      "biosimilar": "Tishtha (ZRC-3276)",
      "phase": "Launched",
      "status": "Approved in India",
      "countries": "India",
      "est_launch": "Mar 2026",
      "probability": 95,
      "strengths_weaknesses": "..."
    }
  ],
  "verified_updates": [
    {
      "source": "FDA",
      "date": "2026-04-28",
      "title": "Short title",
      "summary": "One sentence summary"
    }
  ],
  "social_noise": [
    {
      "user": "@OncoMD",
      "time": "2h ago",
      "post": "Post text",
      "sentiment": "Positive"
    }
  ],
  "ai_insights": "Grok’s deeper reasoning"
}
7. All Code Files
requirements.txt
txtstreamlit
xai-sdk
pandas
python-dotenv
apscheduler
.env (example)
envXAI_API_KEY=sk-...
EMAIL_SENDER=your.email@gmail.com
EMAIL_PASSWORD=your_gmail_app_password
EMAIL_RECIPIENT=your.email@gmail.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
db.py, prompts.py, agent.py, scheduler.py, notifications.py, main.py
→ Use the exact latest versions I provided in previous messages (Batch mode with structured JSON, email alerts, live parsing in all tabs).
8. Quick Start
Bashpip install -r requirements.txt
python -c "from db import init_db; init_db()"
streamlit run main.py          # Terminal 1
python scheduler.py            # Terminal 2
9. Deployment

Deploy on Render.com (Web Service for main.py + Background Worker for scheduler.py)
Connect custom domain aibyf.com (from Vercel) by adding DNS records in Render or Vercel.

Ready for development — this spec contains everything needed to build the complete product.