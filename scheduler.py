"""
scheduler.py — APScheduler weekly surveillance job.

Runs every Sunday at 03:00 AM local time.
Start with: python scheduler.py
"""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from agent import run_surveillance

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [scheduler] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

scheduler = BlockingScheduler(timezone="America/New_York")


@scheduler.scheduled_job(CronTrigger(day_of_week="sun", hour=3, minute=0))
def weekly_job():
    log.info("Starting weekly Opdivo biosimilar surveillance …")
    try:
        data = run_surveillance(use_batch=True)
        log.info("Surveillance complete. Summary: %s", data.get("executive_summary", "—")[:120])
    except Exception as exc:
        log.error("Surveillance failed: %s", exc, exc_info=True)


if __name__ == "__main__":
    log.info("Scheduler started — next run: every Sunday @ 03:00 AM ET")
    log.info("Press Ctrl+C to stop.")
    scheduler.start()
