"""
agent.py — Grok Batch API logic for Opdivo Biosimilar Surveillance.

Uses the official xai-sdk (NOT openai):
  - client.chat.create(model, ...)  →  Chat object
  - chat.append(user(...))          →  add a user message
  - chat.sample()                   →  synchronous completion → Response
  - response.content                →  string reply

  - client.batch.create(name)       →  Batch proto
  - client.batch.add(batch_id, [chat, ...])
  - client.batch.get(batch_id)      →  Batch proto (poll state)
  - client.batch.list_batch_results(batch_id) → ListBatchResultsResponse
    .succeeded[i].response.content  →  string reply

Workflow:
  1. submit_batch_job()  → creates + seals a Batch, returns batch_id
  2. poll_batch_job()    → polls until all requests processed, returns text
  3. run_surveillance()  → orchestrates submit → poll → parse → save → email
"""

import json
import logging
import os
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date as _date, datetime

from dotenv import load_dotenv
from xai_sdk.sync.client import Client
from xai_sdk.chat import user as user_msg

from db import get_latest_report, init_db, save_report, MODEL_FAST, MODEL_FLAGSHIP
from prompts import build_surveillance_prompt

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [agent] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# Build the xai-sdk sync client.
# Raise early with a clear message if the key is missing rather than failing
# silently later; do NOT store the key as a named module attribute.
_api_key = os.getenv("XAI_API_KEY")
if not _api_key:
    raise EnvironmentError("XAI_API_KEY is not set. Add it to your .env file.")
client = Client(api_key=_api_key)
del _api_key  # don't keep the key alive as a named module attribute

MODEL_FAST_DEFAULT = MODEL_FAST         # grok-4-1-fast-reasoning — Batch + Sync
MODEL_FLAGSHIP_DEFAULT = MODEL_FLAGSHIP # grok-4.20-reasoning — high accuracy
MODEL = MODEL_FAST_DEFAULT              # default for backwards-compat references
BATCH_POLL_INTERVAL = 30        # seconds between poll attempts
BATCH_TIMEOUT = 14400           # 4 hours max
BATCH_REQUEST_ID = "opdivo-surveillance-001"

# ── Shared live-status dict (read by Streamlit UI for progress display) ───────
# Written by agent functions; read by main.py via agent.JOB_STATUS.
# Keys: phase/detail plus run-level metadata used by main.py reconciliation.
JOB_STATUS: dict = {
    "phase": "idle",
    "detail": "",
    "run_token": "",
    "result_ready": False,
    "expected_report_run_date": "",
}
_JOB_STATUS_LOCK = threading.Lock()


def _set_status(phase: str, detail: str = "", **extra: object) -> None:
    """Update the shared status dict and log the phase transition."""
    with _JOB_STATUS_LOCK:
        JOB_STATUS["phase"] = phase
        JOB_STATUS["detail"] = detail
        if extra:
            JOB_STATUS.update(extra)
    log.info("[phase] %-15s  %s", phase, detail)


def get_status_snapshot() -> dict:
    """Return a thread-safe full copy of the current job status."""
    with _JOB_STATUS_LOCK:
        return dict(JOB_STATUS)


def mark_job_complete(detail: str = "Complete ✓") -> None:
    """Public helper for main thread to mark completion after external checks."""
    _set_status("done", detail)


def mark_job_error(detail: str) -> None:
    """Public helper for main thread to publish a terminal error status."""
    _set_status("error", detail)


# ─────────────────────────────────────────────────────────────────────────────
# Low-level helpers
# ─────────────────────────────────────────────────────────────────────────────

def _call_chat_raw(prompt: str, model: str | None = None) -> str:
    """Synchronous (non-batch) chat call — used for quick manual runs / fallback.

    This is the unwrapped inner function.  Use _call_chat() for the
    timeout-protected public interface.
    """
    _model = model or MODEL
    _set_status("connecting", f"Opening sync chat with {_model}")
    chat = client.chat.create(model=_model, temperature=0)
    chat.append(user_msg(prompt))
    _set_status("waiting", f"Prompt sent — {_model} is thinking (may take 5–20 min)")
    t0 = time.time()
    response = chat.sample()
    elapsed = time.time() - t0
    log.info("Sync call completed in %.1fs (%.1f min)", elapsed, elapsed / 60)
    _set_status("received", f"Response received in {elapsed:.0f}s — parsing JSON")
    return response.content or ""


def _call_chat(prompt: str, model: str | None = None, timeout_seconds: int = 1800) -> str:
    """Timeout-protected wrapper around _call_chat_raw (default: 30 min).

    If the Grok API hangs, this raises a clean TimeoutError instead of
    blocking the worker thread forever.
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_call_chat_raw, prompt, model)
        try:
            return future.result(timeout=timeout_seconds)
        except TimeoutError as exc:
            log.error("Sync call timed out after %ds", timeout_seconds)
            _set_status("error", f"Sync API call timed out after {timeout_seconds}s")
            raise TimeoutError(
                f"Grok API call exceeded {timeout_seconds}s timeout"
            ) from exc


def _call_openrouter(prompt: str, model: str, timeout_seconds: int = 1800) -> str:
    """Call any model via OpenRouter (Claude, GPT, DeepSeek, etc.)."""
    _api_key = os.getenv("OPENROUTER_API_KEY")
    if not _api_key:
        raise EnvironmentError(
            "OPENROUTER_API_KEY is not set. Add it to your .env file to use non-Grok models."
        )
    _set_status("connecting", f"Opening OpenRouter chat with {model}")
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://biosimintel.com",
            "X-Title": "Opdivo Biosimilar Surveillance",
        },
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        log.error("OpenRouter call failed: %s", exc)
        _set_status("error", f"OpenRouter call failed: {exc}")
        raise RuntimeError(f"OpenRouter API error: {exc}") from exc
    elapsed = time.time() - t0
    log.info("OpenRouter call completed in %.1fs", elapsed)
    _set_status("received", f"Response received in {elapsed:.0f}s — parsing JSON")
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return content


def _call_model(prompt: str, model: str | None = None, timeout_seconds: int = 1800) -> str:
    """Dispatcher — routes to xAI Grok or OpenRouter based on model name."""
    _model = model or MODEL
    if _model.startswith("grok-"):
        return _call_chat(prompt, model=_model, timeout_seconds=timeout_seconds)
    return _call_openrouter(prompt, model=_model, timeout_seconds=timeout_seconds)


# ─────────────────────────────────────────────────────────────────────────────
# Batch API
# ─────────────────────────────────────────────────────────────────────────────

def submit_batch_job(prompt_text: str, model: str | None = None) -> str:
    """Creates a named Batch, adds the surveillance chat request, returns batch_id."""
    _model = model or MODEL
    # 1. Create an empty named batch
    batch = client.batch.create("opdivo-surveillance")
    batch_id = batch.batch_id
    log.info("Batch created: %s [model=%s]", batch_id, _model)
    _set_status("submitting", f"Batch created: {batch_id}")

    # 2. Build the chat request
    chat = client.chat.create(
        model=_model,
        temperature=0,
        batch_request_id=BATCH_REQUEST_ID,
    )
    chat.append(user_msg(prompt_text))

    # 3. Seal + start
    client.batch.add(batch_id=batch_id, batch_requests=[chat])
    log.info("Batch request added & sealed: %s", batch_id)
    _set_status("queued", f"Batch job sealed and queued: {batch_id}")
    return batch_id


def poll_batch_job(batch_id: str) -> str:
    """Polls the Batch until all requests are processed (or timeout).

    A batch is complete when:
        batch_info.state.num_pending == 0
        AND batch_info.state.num_requests > 0

    Then we fetch results via:
        client.batch.list_batch_results(batch_id)
        .succeeded[0].response.content
    """
    deadline = time.time() + BATCH_TIMEOUT
    poll_count = 0
    while time.time() < deadline:
        batch_info = client.batch.get(batch_id)
        state = batch_info.state
        poll_count += 1
        status_detail = (
            f"Poll #{poll_count} — pending={state.num_pending} "
            f"success={state.num_success} error={state.num_error} "
            f"total={state.num_requests}"
        )
        if poll_count % 10 == 0:  # Log only every 10th poll (every 5 minutes)
            _set_status("polling", status_detail)
            log.info(
                "Batch %s — pending=%s success=%s error=%s cancelled=%s total=%s",
                batch_id, state.num_pending, state.num_success,
                state.num_error, state.num_cancelled, state.num_requests,
            )

        if state.num_requests > 0 and state.num_pending == 0:
            # All requests have been processed
            _set_status("retrieving", "All requests complete — fetching results")
            results_page = client.batch.list_batch_results(batch_id)

            if results_page.failed:
                for r in results_page.failed:
                    log.error("Failed request %s: %s", r.batch_request_id, r.error_message)

            for result in results_page.succeeded:
                if result.batch_request_id == BATCH_REQUEST_ID:
                    return result.response.content or ""

            # Fallback: return first succeeded result if ID doesn't match
            if results_page.succeeded:
                return results_page.succeeded[0].response.content or ""

            raise ValueError("Batch completed but no successful results found.")

        if state.num_requests > 0 and state.num_error + state.num_cancelled == state.num_requests:
            raise RuntimeError(f"All requests in batch {batch_id} failed or were cancelled.")

        time.sleep(BATCH_POLL_INTERVAL)

    raise TimeoutError(f"Batch job {batch_id} did not complete within {BATCH_TIMEOUT}s.")


# ─────────────────────────────────────────────────────────────────────────────
# JSON parsing
# ─────────────────────────────────────────────────────────────────────────────

# Known ground-truth entries that must always appear in the output, used as
# a fallback safety net when the model omits or mis-labels them.
_KNOWN_LAUNCHED: list[dict] = [
    {
        "company": "Zydus Lifesciences",
        "biosimilar": "Tishtha (nivolumab biosimilar)",
        "phase": "Launched",
        "status": "First nivolumab biosimilar globally — launched in India (CDSCO approved, 2026).",
        "countries": "India",
        "est_launch": "2026",
        "probability": 100,
        "strengths_weaknesses": "First-mover advantage in India; strong Zydus oncology distribution network. Risk of export into MEA/LATAM markets via Zydus international distribution.",
        "source": "CDSCO approval notice, 2026",
    },
]


def _patch_companies(companies: list[dict]) -> list[dict]:
    """Ensure known ground-truth entries are present and correctly labelled.

    For each entry in _KNOWN_LAUNCHED:
    - If the company already exists in the list but has a wrong phase, fix it.
    - If the company is completely absent, append the canonical entry.
    """
    for known in _KNOWN_LAUNCHED:
        key = known["company"].lower()
        # Find any existing entry whose company name contains the key substring
        matches = [
            i for i, c in enumerate(companies)
            if key.split()[0] in c.get("company", "").lower()   # e.g. "zydus"
        ]
        if matches:
            idx = matches[0]
            existing_phase = companies[idx].get("phase", "")
            if "launch" not in existing_phase.lower():
                log.info(
                    "[patch] Correcting '%s' phase from '%s' → 'Launched'",
                    companies[idx]["company"], existing_phase,
                )
                companies[idx]["phase"] = known["phase"]
                companies[idx]["probability"] = known["probability"]
                companies[idx]["status"] = known["status"]
        else:
            log.info("[patch] Injecting missing entry: %s", known["company"])
            companies.append(dict(known))
    return companies


def parse_grok_response(raw_text: str) -> dict:
    """Strips markdown fences if present, JSON-parses, normalises schema, then applies patches."""
    text = raw_text.strip()
    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        log.error("JSON parse failed: %s", exc)
        # Return a minimal valid dict so the pipeline doesn't crash
        return {
            "parse_error": True,
            "executive_summary": (
                f"[PARSE ERROR] Grok returned invalid JSON. Raw text length: {len(text)}. "
                f"Error: {exc}"
            ),
            "companies": [],
            "verified_updates": [],
            "social_noise": [],
            "my_markets_threat": [],
            "ai_insights": "",
        }

    # ── Guarantee known ground-truth entries are correct ──────────────────────
    if "companies" in data:
        data["companies"] = _patch_companies(data["companies"])

    # ── Normalise my_markets_threat entries for backwards compatibility ────────
    for threat in data.get("my_markets_threat", []):
        # Ensure recommended_actions is always a list (model may return a string)
        if isinstance(threat.get("recommended_actions"), str):
            threat["recommended_actions"] = [threat["recommended_actions"]]
        elif threat.get("recommended_actions") is None:
            threat["recommended_actions"] = ["No immediate action required — maintain watch"]
        # Ensure risk_rationale exists
        if not threat.get("risk_rationale"):
            threat["risk_rationale"] = "No rationale provided."

    # ── Normalise social_noise entries (new schema added platform/signal_type) ─
    for post in data.get("social_noise", []):
        post.setdefault("platform", "X")
        post.setdefault("signal_type", "Regulatory")
        post.setdefault("date", None)
        post.setdefault("url", None)
        post.setdefault("url_verified", False)
        # Enforce trust: if url_verified is False or url is missing, clear the URL
        if not post.get("url_verified") or not post.get("url"):
            post["url"] = None
            post["url_verified"] = False

    # ── Normalise verified_updates (new url / relevance fields) ──────────────
    for update in data.get("verified_updates", []):
        update.setdefault("url", None)
        update.setdefault("relevance_to_lr_markets", "None")

    return data


# ─────────────────────────────────────────────────────────────────────────────
# Main orchestration
# ─────────────────────────────────────────────────────────────────────────────

def run_surveillance(use_batch: bool = True, run_token: str | None = None, model: str | None = None) -> dict:
    """
    Full pipeline:
      1. Submit API job (batch or sync)
      2. Parse JSON
      3. Save to DB (with model_version tag)
      4. Send email alert
    Returns the parsed data dict.
    """
    active_model = model or MODEL_FAST_DEFAULT
    t_start = datetime.now()
    run_token = run_token or t_start.isoformat()
    log.info("=== Surveillance START [model=%s] at %s ===", active_model, t_start.isoformat())
    _set_status(
        "starting",
        "Initialising surveillance run",
        run_token=run_token,
        result_ready=False,
        expected_report_run_date="",
    )

    init_db()

    # Build the prompt at run-time so the model receives today's real date and
    # (when available) the prior report date for incremental-reuse decisions.
    prior_row = get_latest_report() or {}
    prior_run_date: _date | None = None
    try:
        prior_raw = (prior_row.get("run_date") or "")[:10] if prior_row else ""
        if prior_raw:
            prior_run_date = _date.fromisoformat(prior_raw)
    except (ValueError, TypeError):
        prior_run_date = None
    prompt_text = build_surveillance_prompt(_date.today(), prior_run_date)

    if use_batch:
        batch_id = submit_batch_job(prompt_text, model=active_model)
        raw_text = poll_batch_job(batch_id)
    else:
        log.info("Running SYNC call — model=%s", active_model)
        _set_status("connecting", f"Sending prompt to {active_model} via Sync API")
        raw_text = _call_model(prompt_text, model=active_model)

    _set_status("parsing", "Parsing JSON response from Grok")
    data = parse_grok_response(raw_text)
    summary = data.get("executive_summary", "No summary available.")

    _set_status("saving", "Saving report to database")
    save_report(data, summary, model_version=active_model)
    log.info("Report saved to DB [model=%s].", active_model)

    # Capture the exact latest row marker so main.py can verify it loaded
    # the report generated by this run (not an older cached row).
    latest_row = get_latest_report()
    expected_run_date = (latest_row or {}).get("run_date", "")
    _set_status(
        "saving",
        "Report persisted to database",
        result_ready=True,
        expected_report_run_date=expected_run_date,
    )

    t_end = datetime.now()
    duration = (t_end - t_start).total_seconds()
    log.info(
        "=== Surveillance COMPLETE [duration=%.1fs (%.1f min) at %s] ===",
        duration, duration / 60, t_end.isoformat(),
    )
    # Mark done immediately so the main thread can detect completion on the
    # very next reconcile pass without waiting for an extra reconcile cycle.
    mark_job_complete(f"Complete ✓ — Pipeline done in {duration:.0f}s")
    return data


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Opdivo biosimilar surveillance.")
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Use direct sync call instead of batch (for manual runs).",
    )
    args = parser.parse_args()

    result = run_surveillance(use_batch=not args.sync)
    print("\n[agent] Executive Summary:")
    print(result.get("executive_summary", "—"))
