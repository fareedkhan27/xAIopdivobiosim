# Phase 1: Foundation Fixes — Implementation Plan

## Objective
Eliminate critical bugs, security holes, and silent logic failures identified in the audit so the dashboard is safe and accurate for daily use by the BMS Operations team.

---

## Changes Overview

### 1. Fix hardcoded "time to threat" date (`main.py`)
- **Location:** `main.py` line ~1696, inside `_ttt()` function
- **Problem:** `today = _date(2026, 4, 1)` is frozen; all threat timelines are wrong after April 2026.
- **Fix:** Replace with `datetime.now().date()`.
- **Risk:** Zero. Pure logic fix, no UI change.

### 2. Wire up missing report-ready email (`agent.py`)
- **Location:** `agent.py`, inside `run_surveillance()` after `save_report()`
- **Problem:** `send_report_ready_email()` exists in `notifications.py` but is never called. Only high-risk alerts fire.
- **Fix:** Add `send_report_ready_email(data)` call in the success path, wrapped in try/except so an email failure never crashes the pipeline.
- **Risk:** Low. Non-blocking try/except protects the main flow.

### 3. Move hardcoded credentials to environment variables (`main.py`, `.env.example`)
- **Location:** `main.py` lines ~92 (`_CORRECT_PASSWORD`) and ~701 (`_FLAGSHIP_CODE`)
- **Problem:** Secrets are in source code; cannot rotate without redeploy.
- **Fix:**
  - Read `ACCESS_CODE` and `FLAGSHIP_CODE` from `os.getenv()` with sensible defaults for backward compat.
  - Update `.env.example` to document these new variables.
  - Update `AGENTS.md` security section.
- **Risk:** Low. Defaults preserve current behavior if env vars are absent.

### 4. XSS hardening — escape Grok-generated HTML (`main.py`)
- **Location:** All `st.markdown(..., unsafe_allow_html=True)` blocks that inject dynamic Grok strings.
- **Problem:** If Grok returns `<script>` or event-handler payloads, they execute in the browser.
- **Fix:**
  - Import `html` (stdlib) at top of `main.py`.
  - Apply `html.escape()` to every Grok-sourced string before f-string interpolation into HTML templates.
  - Affected fields: `company`, `biosimilar`, `phase`, `status`, `countries`, `est_launch`, `strengths_weaknesses`, `source`, `user`, `post`, `sentiment`, `title`, `summary`, `ai_insights`, `executive_summary`.
- **Risk:** Medium. Touches many UI lines; requires careful verification that no intentional HTML from Grok is broken. (Grok should not output HTML anyway per prompt rules.)

### 5. Add JSON parse error handling (`agent.py`)
- **Location:** `agent.py`, inside `parse_grok_response()`
- **Problem:** `json.loads(text)` raises unhandled exception on malformed JSON, crashing a 4-hour batch job.
- **Fix:** Wrap `json.loads()` in try/except. On failure:
  1. Log the raw text snippet (first 2 KB).
  2. Return a minimal valid dict with `parse_error` flag and `executive_summary` explaining the failure.
  3. `run_surveillance()` should still save this error report to DB so the UI shows something instead of hanging.
- **Risk:** Low. Improves resilience.

### 6. Replace `print()` with `log.info()` (`agent.py`)
- **Location:** `_patch_companies()` lines ~244 and ~252
- **Problem:** Inconsistent logging.
- **Fix:** Replace `print(...)` with `log.info(...)`.
- **Risk:** Zero.

### 7. Update `.env.example` to match reality
- **Add:** `XAI_API_KEY`, `RESEND_API_KEY`, `DB_PATH`, `ACCESS_CODE`, `FLAGSHIP_CODE`
- **Remove:** Nothing (keep old SMTP vars for fallback)
- **Risk:** Zero.

---

## Files Touched
| File | Lines of Change | Nature |
|------|-----------------|--------|
| `main.py` | ~60 | Logic fix, env vars, XSS escaping |
| `agent.py` | ~25 | Email call, JSON error handling, logging |
| `.env.example` | ~8 | New variables |
| `AGENTS.md` | ~5 | Update security note |

---

## Quality Gates (Before Marking Complete)
- [ ] `python -c "from main import *"` loads without import errors
- [ ] `streamlit run main.py` starts; login gate accepts code from env var
- [ ] Dashboard renders with mock data; no broken HTML visible
- [ ] `python -c "from agent import parse_grok_response; parse_grok_response('not json')"` returns error dict instead of crashing
- [ ] `python -c "from notifications import send_report_ready_email; ..."` can be invoked without error (manual or mock)
- [ ] `ruff check main.py agent.py` passes (or only pre-existing issues)

---

## Rollback Plan
- All changes are in a single feature branch.
- If anything breaks: `git checkout main` and redeploy.
- Database schema is unchanged, so data is safe.

---

## Risk Assessment
- **Overall:** Medium (main risk is the XSS string-replacement sweep across many UI lines)
- **Mitigation:** Use `html.escape()` only on values known to come from Grok; leave static HTML templates untouched.

---

## Estimated Effort
1–2 hours of focused editing + 30 min of manual smoke testing.
