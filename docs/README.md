# Opdivo (Nivolumab) Biosimilar Surveillance Tool

**A fully automated competitive intelligence dashboard** that tracks biosimilar development for **Opdivo (nivolumab)** in real time.

It monitors clinical trials, regulatory filings (FDA, EMA, etc.), launches, and social discussions — all powered by **Grok API** with **Batch mode** for maximum cost efficiency.

---

## 🎯 Key Features

- Automatic **weekly surveillance** (runs every Sunday)
- Uses Grok’s real-time web + X (Twitter) search tools
- Clear separation between **Verified Intelligence** and **Social Noise**
- Pipeline tracking with launch probability scores
- Email alerts when new reports are ready
- Professional dark-mode dashboard
- Export data to CSV
- Extremely low running cost (~$0.05 per weekly run)

---

## 🛠 Tech Stack

| Component       | Technology                  |
|-----------------|-----------------------------|
| Dashboard       | Streamlit                   |
| AI / Search     | xAI Grok API (Batch mode)   |
| Database        | SQLite                      |
| Scheduler       | APScheduler                 |
| Notifications   | Email (Gmail SMTP)          |
| Language        | Python 3.11+                |

---

## 📁 Project Structure
```

opdivo-surveillance/ ├── .env # ← Put your keys here ├── requirements.txt ├── README.md ├── IMPLEMENTATION_PLAN.md ├── WIREFRAMES_UI_SPEC.md ├── db.py ├── prompts.py ├── agent.py # Main Grok Batch logic ├── scheduler.py # Weekly automation ├── notifications.py # Email alerts ├── main.py # Dashboard └── opdivo_reports.db # Auto-created

text

````
---

## 🚀 Quick Start (Step-by-Step)

### 1. Setup Environment
```bash
pip install -r requirements.txt
````

### 2. Create .env file

env

`XAI_API_KEY=sk-...................... # Get from https://console.x.ai # Email alerts (Gmail recommended) EMAIL_SENDER=your.email@gmail.com EMAIL_PASSWORD=your_gmail_app_password EMAIL_RECIPIENT=your.email@gmail.com SMTP_SERVER=smtp.gmail.com SMTP_PORT=587`

> **Tip**: Create a Gmail App Password (not your regular password).

### 3. Initialize Database

Bash

```
python -c "from db import init_db; init_db()"
```

### 4. Run the Application

**Terminal 1** — Start the Dashboard:

Bash

```
streamlit run main.py
```

**Terminal 2** — Start the Scheduler:

Bash

```
python scheduler.py
```

Open the URL shown in the terminal (usually http://localhost:8501).

---

## 📊 How to Use the Dashboard

1. Go to the **Dashboard** tab
2. Click **"Run New Surveillance (Batch)"** (first time only)
3. Wait for Grok to finish processing (usually a few hours)
4. Refresh the page — all tabs will update with fresh data
5. The scheduler will automatically run every **Sunday at 3:00 AM**

---

## 📧 Email Alerts

You will automatically receive an email when a new report is ready, including:

- Executive Summary
- Key alerts
- Link to the dashboard

---

## 💰 Cost

- **Weekly run**: ~$0.05 – $0.15 (thanks to Batch mode — 50% cheaper)
- **Monthly cost**: Usually under $1
- **Hosting**: Free tier on Render.com / Railway.app

---

## 📋 Available Dashboard Pages

- **Dashboard** — Overview, KPIs, latest updates
- **Pipeline Tracker** — Sortable table of all companies
- **Verified Intelligence** — Official regulatory & clinical data
- **Social Noise** — X (Twitter) posts + sentiment analysis
- **AI Insights** — Grok’s reasoning and probability analysis
- **Timeline** — Competitive Gantt-style view

---

## 🚀 Deployment (Production)

Recommended platform: **Render.com**

1. Push code to GitHub
2. Create a **Web Service** for main.py
3. Create a **Background Worker** for scheduler.py
4. Add all variables from .env
5. Deploy
---

## 🔄 Future Enhancements

- Multi-molecule support (Keytruda, etc.)
- Advanced charts & PDF export
- User authentication
- Historical comparison
- Mobile app version

---

## 📄 Documentation

- IMPLEMENTATION_PLAN.md → Full development plan
- WIREFRAMES_UI_SPEC.md → Complete wireframes & data mapping

---

**Built for competitive intelligence in the biopharma industry.**

---
