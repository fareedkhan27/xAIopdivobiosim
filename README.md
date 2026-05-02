# 🧬 Opdivo (Nivolumab) Biosimilar Surveillance System

> **BMS Global Oncology Operations — Competitive Intelligence Command Center**  
> *Real-time biosimilar threat monitoring across 37 LR priority markets*

---

## 1. Executive Overview

This project is a **production-grade competitive intelligence dashboard** built for Bristol-Myers Squibb (BMS) Global Oncology Operations. It automates the surveillance of nivolumab (Opdivo) biosimilar threats across **37 countries** in CEE/EU, LATAM, and MEA regions.

The system integrates **four frontier AI models** (Grok, Claude, Gemini, DeepSeek) via a multi-backend architecture, enabling BMS teams to compare model accuracy, identify pipeline threats, and receive decision-grade strategic assessments.

**Live URL:** `https://biosimintel.com`  
**Railway Project:** `xAIopdivobiosim`  
**Volume:** `opdivo-db-volume`

---

## 2. The Challenge

### Business Context
BMS manages Opdivo (nivolumab) across **37 LR markets** with three operating models:
- **LPM** (Limited Promotional Model): 17 countries
- **OPM** (Optimized Promotional Model): 13 countries
- **Passive**: 3 countries

### Competitive Threat
16+ companies are developing nivolumab biosimilars, including:
- **Launched:** Zydus (Tishtha, India), Biocad (Nivabulin, CIS)
- **Phase III:** Amgen (ABP 206), Boan Biotech (BA6101)
- **Pre-clinical / Early:** Sandoz, mAbxience, Xbrane/Intas, and others

### The Problem
Before this system, competitive intelligence was:
- **Manual** — analysts checking 16+ company websites, registries, and news sources
- **Slow** — weekly cycles taking 8+ hours of analyst time
- **Inconsistent** — no standardized threat scoring or country-level risk mapping
- **Reactive** — threats discovered after launches had already occurred

### The Objective
Build an **automated, AI-powered surveillance engine** that:
1. Monitors all 16 competitors continuously
2. Tracks pipeline phases, regulatory filings, and launch activity
3. Scores country-level risk (High / Medium / Low / None)
4. Generates board-ready executive summaries
5. Enables model comparison to identify the most accurate AI for each task

---

## 3. Solution Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  USER / SCHEDULER                                                        │
│  ├─ Manual: "Run Flagship" (on-demand, model-selectable)                │
│  └─ Automated: Weekly Sunday 3 AM ET (Grok batch, cost-optimized)      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  AI ORCHESTRATION LAYER (agent.py)                                     │
│  ├─ Grok 4.3 → xAI Direct API (native web_search + x_search)            │
│  ├─ Gemini 2.5 Pro → OpenRouter (Google Search grounding)              │
│  ├─ Claude Sonnet 4.5 → OpenRouter (best reasoning + JSON)            │
│  └─ DeepSeek V4 Pro → OpenRouter (deep chains, cheapest)               │
│                                                                         │
│  Dispatcher: _call_model() routes by slug prefix                      │
│  ├─ grok-* → xai-sdk (gRPC)                                            │
│  └─ anthropic/*, google/*, deepseek/* → urllib POST (OpenRouter HTTP)   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PROMPT ENGINE (prompts.py)                                              │
│  ├─ build_surveillance_prompt(run_date, prior_run_date)                │
│  │   └─ Injects real date, company list (16), LR markets (37),         │
│  │      action menu (17), probability rubric (8 anchors)              │
│  └─ OPDIVO_SURVEILLANCE_PROMPT (backward-compatible constant)          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  JSON PARSER (agent.py)                                                  │
│  ├─ parse_grok_response() → structured dict                            │
│  ├─ Graceful fallback on JSONDecodeError → minimal error dict           │
│  └─ _patch_companies() → ground-truth patches for known launches         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PERSISTENCE LAYER (db.py)                                               │
│  ├─ SQLite (WAL mode, append-only, check_same_thread=False)             │
│  ├─ save_report(raw_json, summary, model_version)                      │
│  ├─ get_all_reports() / get_latest_report()                            │
│  └─ _safe_add_column() → zero-downtime schema evolution                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  DASHBOARD LAYER (main.py + theme.py)                                    │
│  ├─ 9 tabs: Dashboard, Competitor Pipeline, Verified Intelligence,       │
│  │   Social Noise, AI Insights, Timeline, LR Markets, History,          │
│  │   🧪 Model Lab                                                       │
│  ├─ Dual Theme: Presentation Mode (white) + Dark Mode (slate)          │
│  ├─ Model selection dropdown with backend indicator                     │
│  └─ Flagship code gate (env-var protected)                             │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Dashboard** | Streamlit | Interactive UI, 9 tabs, responsive CSS |
| **AI / Search** | xAI Grok API + OpenRouter | Multi-model orchestration |
| **Database** | SQLite (WAL mode) | Append-only persistence, zero-downtime |
| **Scheduler** | APScheduler | Weekly automated runs (Sunday 3 AM ET) |
| **Email** | Resend API (HTTP) | Manual test emails from UI |
| **Charts** | Plotly + pandas | Probability bars, timelines, data tables |
| **Language** | Python 3.11+ | Type hints, f-strings, dataclasses |
| **Linting** | ruff | Zero-tolerance code quality |
| **Deployment** | Railway.app | Web Service + Background Worker |
| **Domain** | Cloudflare → Railway | `biosimintel.com` |

---

## 5. AI Model Strategy

### The 4-Model Stack

| # | Model | Backend | Role | Cost (per 1M out) | Key Strength |
|---|-------|---------|------|-------------------|--------------|
| 1 | **Grok 4.3** | xAI Direct | **Live Surveillance** | $2.50 | Native web + X search, real-time data |
| 2 | **Gemini 2.5 Pro** | OpenRouter | **Factual Retrieval** | $10.00 | Google Search grounding, best JSON |
| 3 | **Claude Sonnet 4.5** | OpenRouter | **Strategic Synthesis** | $15.00 | Best reasoning, citation discipline |
| 4 | **DeepSeek V4 Pro** | OpenRouter | **Cost Analysis** | $3.48 | Deep chains, probability scoring |

### Why This Stack?

**Grok** is the only model with first-party X (Twitter) search — critical for pharma KOL chatter, company communications, and real-time tender announcements.

**Gemini** provides Google Search grounding via OpenRouter, making it the best fallback for web-based clinical trial and regulatory retrieval if Grok's x_search misses something.

**Claude** has the highest JSON schema adherence and reasoning quality. It produces the cleanest executive summaries and most defensible risk rationales.

**DeepSeek** is the cheapest deep-reasoning model. It excels at probability rubric application and threat timeline estimation.

### What We Removed (And Why)

| Removed | Reason |
|---------|--------|
| **GPT 5.5** | Poorest performer in head-to-head testing. Training-data-only with hallucination issues. |
| **Keytruda scope** | Added complexity broke JSON reliability. Scope narrowed to Opdivo-only for MVP stability. |
| **pipeline_tracker schema** | Replaced `companies` array with `pipeline_tracker` + `regulatory_tracker` + `launch_monitor` — too complex for Grok's JSON generator. Reverted to simpler schema. |

### Model Comparison Framework

The **🧪 Model Lab** tab enables objective comparison:
- **Executive Summary Showdown** — side-by-side summaries per model
- **Who Found Which Competitors?** — per-model company detection accuracy
- **Threat Landscape** — High/Medium risk country counts per model
- **URL Quality** — verified URLs vs. total updates per model
- **Winner Badge** — Score = companies×2 + high-risk markets×3 + verified URLs

---

## 6. Key Features Implemented

### Phase 1: Foundation Fixes
- ✅ XSS hardening (`html.escape()` on all Grok-rendered strings)
- ✅ Hardcoded date fix (`_ttt()` uses `date.today()`)
- ✅ Auto-email removal (only manual Test Send Email remains)
- ✅ Auth moved to env vars (`ACCESS_CODE`, `FLAGSHIP_CODE`)
- ✅ `.env.example` synced with all real variables

### Phase 2: Thread Safety
- ✅ 5-hour watchdog timeout (kills zombie loops)
- ✅ Polling sleep 5s → 15s (66% less server blocking)
- ✅ `_ACTIVE_THREAD` hard guard (prevents double-click race)

### Phase 3: API Hardening
- ✅ 30-minute sync API timeout (ThreadPoolExecutor)
- ✅ Graceful timeout propagation to UI

### Phase 4: UI Polish
- ✅ Dual Theme System (Presentation Mode + Dark Mode)
- ✅ Progress banner with CSS heartbeat animation
- ✅ Time-based `st.progress()` bar
- ✅ Model tags in History (colored badges)

### Phase 5: Multi-Model Architecture
- ✅ Model selection dropdown (4 models)
- ✅ Backend indicator (live search vs. training data)
- ✅ Flagship code gate (password-protected)
- ✅ `_call_model()` dispatcher (Grok gRPC vs. OpenRouter HTTP)

### Phase 6: Prompt Engineering
- ✅ Runtime date injection (`build_surveillance_prompt()`)
- ✅ Canonical constants (16 companies, 37 countries, 17 actions, 8 probability anchors)
- ✅ Self-validation rules (H1–H7)
- ✅ Mini example for schema guidance

### Phase 7: Competitor Pipeline Tracker
- ✅ Dedicated tab with rich table (Company, Biosimilar, Phase, Status, Countries, Est. Launch, Probability, Notes)
- ✅ Phase badges, probability bar charts, CSV export
- ✅ Filters by phase and country

### Phase 8: Model Lab
- ✅ Side-by-side model comparison
- ✅ Schema-agnostic extraction (handles both `companies` and `pipeline_tracker` legacy)
- ✅ Robust model name resolution (handles `None` and unknown slugs)
- ✅ Winner scoring based on actual findings

---

## 7. Data Flow & Security

### Security Principles
1. **Append-only database** — `db.py` forbids DELETE, DROP TABLE, TRUNCATE
2. **Schema migrations** — `_safe_add_column()` only; no destructive changes
3. **XSS prevention** — All Grok-generated strings escaped before HTML rendering
4. **Secret handling** — API keys deleted from memory after use (`del _api_key`)
5. **Unverified URLs** — Stripped or rendered non-clickable in social noise

### Data Flow
```
User clicks "Run Flagship"
  → Sidebar validates FLAGSHIP_CODE
  → _ACTIVE_THREAD checks (is_alive guard)
  → Thread spawns with selected_model
    → agent.run_surveillance(use_batch=False, model=selected_model)
      → build_surveillance_prompt(date.today(), prior_date)
      → _call_model(prompt, model)
        ├─ grok-* → xai-sdk → native web + X search
        └─ others → urllib POST → OpenRouter → model-specific search
      → parse_grok_response(raw_text)
        ├─ Valid JSON → db.save_report(data, model_version=selected_model)
        └─ Invalid → minimal error dict (parse_error: true)
      → UI polls every 15s via st.rerun()
        ├─ Job completes → "Pipeline data refreshed"
        └─ 5h timeout → "Job timed out (5h max)"
```

---

## 8. Deployment

### Railway Configuration
- **Project:** `xAIopdivobiosim`
- **Volume:** `opdivo-db-volume` (SQLite persistence)
- **Services:** Web Service (Streamlit) + Background Worker (Scheduler)
- **Domain:** `biosimintel.com` (Cloudflare → Railway)

### Environment Variables
```bash
# AI APIs
XAI_API_KEY=your_xai_key          # Grok direct
OPENROUTER_API_KEY=sk-or-...      # Claude, Gemini, DeepSeek

# Auth
ACCESS_CODE=your_access_code      # Login gate
FLAGSHIP_CODE=your_flagship_code  # Run Flagship gate

# Infrastructure
DB_PATH=opdivo_surveillance.db    # SQLite file (Railway Volume)
RESEND_API_KEY=re_...             # Test Email
RESEND_FROM_EMAIL=intelligence@biosimintel.com
```

### Local Development
```bash
git clone <repo>
cd opdivo-surveillance
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run main.py
# Scheduler: python scheduler.py (separate terminal)
```

---

## 9. Quality Gates

Every code change must pass:
1. `ruff check .` — zero errors
2. `python -c "import agent"` — no import failures
3. `streamlit run main.py` — starts without crash
4. Login gate works with env-var codes
5. Model dropdown routes correctly (Grok → xAI, others → OpenRouter)
6. Report saves with `model_version` in DB
7. History renders old reports (backward compatibility)

---

## 10. Lessons Learned

### What Worked
- **Additive architecture** — New tabs (Pipeline Tracker, Model Lab) without breaking existing flow
- **Model-agnostic dispatcher** — `_call_model()` made adding/removing models trivial
- **Theme separation** — `theme.py` isolated CSS from business logic
- **SQLite WAL** — Zero-downtime schema evolution, append-only safety
- **Phase-by-phase execution** — Foundation → Thread Safety → API → UI → Models → Prompts → Features

### What Didn't Work
- **Schema over-engineering** — Adding `pipeline_tracker` + `regulatory_tracker` + `launch_monitor` + Keytruda scope broke Grok's JSON generator. **Lesson:** Keep the core schema flat and stable. Add fields, not arrays.
- **GPT 5.5** — Training-data-only models hallucinate on pharmaceutical intel. **Lesson:** Only models with live search (Grok, Gemini, Perplexity) are viable for surveillance.
- **X/Twitter over-emphasis** — Social Noise tab produced low-signal chatter. **Lesson:** Regulatory and clinical trial data (web_search) is 10× more valuable than social sentiment for biosimilar tracking.
- **Batch mode confusion** — "Batch (50% cheaper)" vs. "Sync" created UX mismatch. **Lesson:** Single clear path (Run Flagship = sync, scheduler = batch) with honest labeling.

### Pivot Decisions
| Decision | Before | After | Rationale |
|----------|--------|-------|-----------|
| Scope | Opdivo + Keytruda | **Opdivo only** | Keytruda broke JSON reliability; no user requirement for it |
| Schema | `companies` only | `companies` + `verified_updates` + `social_noise` + `my_markets_threat` | Proven stable across 50+ runs |
| Model 4 | GPT 5.5 | **Gemini 2.5 Pro** | GPT hallucinated; Gemini has live search |
| UI Mode | Dark-only | **Presentation Mode default** | Senior management (50+) couldn't read thin green fonts on black |
| Pipeline | Two tabs | **One "Competitor Pipeline" tab** | Redundant pipeline trackers confused users |

---

## 11. Handoff Notes for Next Maintainer

### Critical Files
| File | Responsibility | Change Risk |
|------|---------------|-------------|
| `prompts.py` | Prompt engineering, schema definition | **HIGH** — Any schema change breaks `main.py` rendering |
| `agent.py` | API dispatch, JSON parsing | **MEDIUM** — `_call_model()` is the routing heart |
| `main.py` | UI, tabs, thread management | **MEDIUM** — `st.session_state` is not thread-safe |
| `db.py` | Data safety, migrations | **LOW** — Append-only design is defensive |
| `theme.py` | CSS, responsive design | **LOW** — Purely presentational |

### Safe Changes
- Add new fields to JSON schema (additive only)
- Add new models to `_AVAILABLE_MODELS` (if OpenRouter-compatible)
- Add new dashboard tabs (follow existing pattern)
- Update company list in `COMPANIES` constant

### Dangerous Changes
- Rename JSON schema fields (breaks historical reports)
- Remove `social_noise` or `companies` arrays (breaks `main.py` rendering)
- Modify `_call_model()` dispatcher logic (breaks routing)
- Change SQLite schema without `_safe_add_column()`
- Touch `scheduler.py` batch flow (breaks weekly automation)

### Known Technical Debt
1. `main.py` is ~2,000 lines — could benefit from Streamlit multipage refactor
2. No automated test suite — all verification is manual
3. No Dockerfile — deployment relies on Railway's Python environment
4. OpenRouter models lack live search (except Gemini, if grounding works) — social_noise quality varies
5. `urllib.request` used for OpenRouter — could upgrade to `requests` for retries/timeouts

---

## 12. Future Roadmap

### Immediate (Next 30 Days)
- [ ] Add Grok 4.3 slug to dropdown (replace or supplement Grok 4.1)
- [ ] Test Gemini 2.5 Pro Google Search grounding via OpenRouter
- [ ] If Gemini grounding fails, swap to **Perplexity Sonar Pro**
- [ ] Run head-to-head comparison: Grok 4.3 vs. Grok 4.1 in Model Lab

### Short-Term (Next 90 Days)
- [ ] **Monthly Strategic Synthesis** — Claude Opus 4.5 reads 4 weekly Grok reports and writes a board-ready strategic memo
- [ ] **Time-series trends** — "How did Zydus probability change week-over-week?"
- [ ] **Export to PowerPoint** — One-click deck generation for manager presentations
- [ ] **Alert thresholds** — Auto-flag when competitor probability crosses 75% (BLA submitted)

### Long-Term (Next 6 Months)
- [ ] **Two-stage architecture** — Grok collects raw evidence → Claude synthesizes final report
- [ ] **X API integration** — Direct Twitter API for social_noise (if Grok's x_search is insufficient)
- [ ] **Automated email digests** — Weekly strategic briefing auto-sent to regional leads
- [ ] **Multi-molecule expansion** — Keytruda (pembrolizumab) and other IO assets (with schema v2)

---

## 13. Acknowledgments

Built by **Fareed Khan** for BMS Global Oncology Operations.  
Architecture guidance and phased implementation planning by **Kimi K2.6 (Moonshot AI)**.  
AI model evaluation and prompt engineering audits by **Claude Sonnet 4.5 (Anthropic)**.

---

## 14. License & Confidentiality

> **Internal Use Only — BMS Confidential**  
> This system processes competitive intelligence and strategic data. Do not distribute externally without BMS Legal and Corporate Affairs approval.

---

*End of Project README — Opdivo Biosimilar Surveillance v1.0*  
*Last updated: 2026-05-02*
