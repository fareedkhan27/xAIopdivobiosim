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
import os
import time

from dotenv import load_dotenv
from xai_sdk.sync.client import Client
from xai_sdk.chat import user as user_msg

from db import init_db, save_report
from notifications import send_email_alert
from prompts import OPDIVO_SURVEILLANCE_PROMPT

load_dotenv()

# Build the xai-sdk sync client.
# Raise early with a clear message if the key is missing rather than failing
# silently later; do NOT store the key as a named module attribute.
_api_key = os.getenv("XAI_API_KEY")
if not _api_key:
    raise EnvironmentError("XAI_API_KEY is not set. Add it to your .env file.")
client = Client(api_key=_api_key)
del _api_key  # don't keep the key alive as a named module attribute

MODEL = "grok-3-mini-fast"      # switch to grok-3-latest or grok-4 when available
BATCH_POLL_INTERVAL = 30        # seconds between poll attempts
BATCH_TIMEOUT = 14400           # 4 hours max
BATCH_REQUEST_ID = "opdivo-surveillance-001"


# ─────────────────────────────────────────────────────────────────────────────
# Low-level helpers
# ─────────────────────────────────────────────────────────────────────────────

def _call_chat(prompt: str) -> str:
    """Synchronous (non-batch) chat call — used for quick manual runs / fallback.

    Pattern:
        chat = client.chat.create(model, temperature=...)
        chat.append(user_msg("..."))
        response = chat.sample()       # blocks until model replies
        return response.content        # plain string
    """
    chat = client.chat.create(model=MODEL, temperature=0)
    chat.append(user_msg(prompt))
    response = chat.sample()
    return response.content or ""


# ─────────────────────────────────────────────────────────────────────────────
# Batch API  (50 % cost savings vs. synchronous calls)
# ─────────────────────────────────────────────────────────────────────────────

def submit_batch_job() -> str:
    """Creates a named Batch, adds the surveillance chat request, and returns
    the batch_id.

    xai-sdk batch pattern:
        batch = client.batch.create(batch_name)
        chat  = client.chat.create(model, batch_request_id=..., ...)
        chat.append(user_msg("..."))
        client.batch.add(batch_id=batch.batch_id, batch_requests=[chat])
        # Batch is now sealed and processing begins automatically.
    """
    # 1. Create an empty named batch
    batch = client.batch.create("opdivo-surveillance")
    batch_id = batch.batch_id
    print(f"[agent] Batch created: {batch_id}")

    # 2. Build the chat request (NOT executed yet — will be sent to the batch)
    chat = client.chat.create(
        model=MODEL,
        temperature=0,
        batch_request_id=BATCH_REQUEST_ID,   # lets us match results later
    )
    chat.append(user_msg(OPDIVO_SURVEILLANCE_PROMPT))

    # 3. Add the request to the batch (this seals + starts processing)
    client.batch.add(batch_id=batch_id, batch_requests=[chat])
    print(f"[agent] Batch request added & sealed: {batch_id}")
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
    while time.time() < deadline:
        batch_info = client.batch.get(batch_id)
        state = batch_info.state
        print(
            f"[agent] Batch {batch_id} — "
            f"pending={state.num_pending} success={state.num_success} "
            f"error={state.num_error} cancelled={state.num_cancelled} "
            f"total={state.num_requests}"
        )

        if state.num_requests > 0 and state.num_pending == 0:
            # All requests have been processed
            results_page = client.batch.list_batch_results(batch_id)

            if results_page.failed:
                for r in results_page.failed:
                    print(f"[agent] Failed request {r.batch_request_id}: {r.error_message}")

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
        "strengths_weaknesses": "First-mover advantage in India; strong Zydus oncology distribution network.",
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
                print(
                    f"[agent][patch] Correcting '{companies[idx]['company']}' "
                    f"phase from '{existing_phase}' → 'Launched'"
                )
                companies[idx]["phase"] = known["phase"]
                companies[idx]["probability"] = known["probability"]
                companies[idx]["status"] = known["status"]
        else:
            print(f"[agent][patch] Injecting missing entry: {known['company']}")
            companies.append(dict(known))
    return companies


def parse_grok_response(raw_text: str) -> dict:
    """Strips markdown fences if present, JSON-parses, then applies ground-truth patches."""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    data = json.loads(text)
    # Post-process: guarantee known launched products are always correct
    if "companies" in data:
        data["companies"] = _patch_companies(data["companies"])
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Main orchestration
# ─────────────────────────────────────────────────────────────────────────────

def run_surveillance(use_batch: bool = True) -> dict:
    """
    Full pipeline:
      1. Submit Batch job (or sync call)
      2. Parse JSON
      3. Save to DB
      4. Send email alert
    Returns the parsed data dict.
    """
    init_db()

    if use_batch:
        batch_id = submit_batch_job()
        raw_text = poll_batch_job(batch_id)
    else:
        print("[agent] Running synchronous (non-batch) call …")
        raw_text = _call_chat(OPDIVO_SURVEILLANCE_PROMPT)

    data = parse_grok_response(raw_text)
    summary = data.get("executive_summary", "No summary available.")
    save_report(data, summary)
    print("[agent] Report saved to DB.")

    try:
        send_email_alert(summary)
        print("[agent] Email alert sent.")
    except Exception as exc:
        print(f"[agent] Email failed (non-fatal): {exc}")

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
        help="Use synchronous call instead of Batch API (faster, more expensive).",
    )
    args = parser.parse_args()

    result = run_surveillance(use_batch=not args.sync)
    print("\n[agent] Executive Summary:")
    print(result.get("executive_summary", "—"))
