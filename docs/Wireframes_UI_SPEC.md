
````
# Opdivo Biosimilar Surveillance Tool - Wireframes & UI Specification

**Purpose**: This document provides complete low-fidelity wireframes and detailed layout specifications for the developer/designer to build the exact UI and connect data points from Grok’s structured JSON.

**Style Guidelines**:
- Dark mode (black/gray background, teal/blue accents)
- Clean, modern biotech dashboard look
- Left sidebar navigation (fixed)
- Responsive (desktop-first)
- Use Tailwind or Streamlit components

## 1. Login / Onboarding Screen

**Layout**:
- Centered card (400px wide)
- Logo + Title at top
- Email + Password fields
- “Sign in with X” button (primary)
- “Create Account” link
- Footer with copyright

**Data Points**: None (static)

---

## 2. Dashboard Overview (Home)

**Left Sidebar**: Navigation (active: Dashboard)

**Main Content**:
- Top Navbar: Logo | Search | Live Status | User
- KPI Cards (4 columns):
  - Companies Monitored
  - New Alerts Today
  - Biosimilars Launched
  - Avg Launch Probability
- Section: Latest Verified Updates (4 cards)
- Section: Quick AI Insights (summary box)
- Bottom: Last Updated timestamp + “Run New Surveillance” button

**Data Connections**:
- `executive_summary`
- `verified_updates` (first 4 items)

---

## 3. Pipeline Tracker

**Main Content**:
- Filter row: Company | Phase | Country | Search
- Export button
- Large sortable Data Table with columns:
  - Company
  - Biosimilar Name
  - Current Phase
  - Trial Status
  - Targeted Countries (flags)
  - Est. Launch
  - Launch Probability (progress bar + %)
  - Last Updated

**Data Source**: `companies` array from JSON

---

## 4. Verified Intelligence

**Main Content**:
- Filter: Official Sources only
- Vertical list of expandable cards:
  - Source icon + Date
  - Title
  - Short summary
  - “View Full Document” button

**Data Source**: `verified_updates` array

---

## 5. Social Noise

**Layout**: Two-column
- Left (70%): Scrollable feed of X posts
  - Avatar / Username / Time
  - Post text
  - Sentiment badge (🟢 Positive / 🟠 Neutral / 🔴 Negative)
- Right Sidebar (30%):
  - Sentiment Pie Chart
  - Top Keywords cloud
  - Refresh button

**Data Source**: `social_noise` array

---

## 6. AI Insights

**Layout**: Grid
- Executive Summary (bullets)
- Competitive Risk Heatmap (colored grid)
- Grok’s Reasoning (text box)
- Bottom: Timeline preview

**Data Source**: `ai_insights` + `executive_summary`

---

## 7. Timeline

**Main Content**:
- Horizontal Gantt chart (next 24 months)
- Rows = Companies
- Columns = Quarters/Phases (Pre-clinical → Phase I → II → III → Launch)
- Color-coded bars

**Data Source**: Parsed from `companies` + `ai_insights`

---

## Navigation Sidebar (Common to All Pages)

- Dashboard
- Pipeline Tracker
- Verified Intelligence
- Social Noise
- AI Insights
- Timeline
- Alerts / History
- Settings
- Scheduler Status (Start/Stop)

---

## Data Flow from Grok JSON

```json
{
  "executive_summary": "...",
  "companies": [ ... ],           // → Pipeline Tracker + Timeline
  "verified_updates": [ ... ],    // → Verified Intelligence + Dashboard
  "social_noise": [ ... ],        // → Social Noise
  "ai_insights": "..."            // → AI Insights
}
````

**JSON Parsing Note**: Use json.loads(report['raw_json']) in main.py.

## Color Palette

- Primary: Teal (#00D4C8)
- Accent: Blue (#3B82F6)
- Background: #111827
- Text: White / Light Gray
- Positive: Green, Negative: Red

## Responsive Behavior

- Desktop: Full layout as described
- Tablet/Mobile: Collapse sidebar, stack cards

---

**Implementation Priority**:

1. Sidebar + Navigation
2. Dashboard Overview
3. Pipeline Tracker (table)
4. Verified Intelligence
5. Social Noise
6. AI Insights
7. Timeline
8. Connect live JSON data

**Reference Images**: Use the wireframe images generated earlier in this conversation as visual guides.

**Deliverables Expected**:

- Fully functional Streamlit dashboard matching this spec
- All tabs pulling live data from SQLite + Grok JSON
- Clean, professional UI

**Status**: Ready for development