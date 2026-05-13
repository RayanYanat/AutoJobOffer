#!/usr/bin/env python3
"""
AutoJobOffer — Automated job alert system with Telegram notifications.

Usage:
    python main.py              # Run a single scan
    python main.py --test       # Test Telegram connection
    python main.py --stats      # Show database stats
    python main.py --loop 30    # Run every 30 minutes
"""

import os
import sys
import time
import logging
import argparse
import yaml
from dotenv import load_dotenv

from src.database import JobDatabase
from src.notifier import TelegramNotifier
from src.engine import JobEngine

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="AutoJobOffer — Job Alert System")
    parser.add_argument("--test", action="store_true", help="Test Telegram connection")
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument("--loop", type=int, metavar="MINUTES", help="Run every N minutes")
    parser.add_argument("--no-notify", action="store_true", help="Run without sending notifications")
    parser.add_argument("--seed", action="store_true", help="First run: scan all jobs and save to DB without notifying")
    args = parser.parse_args()

    # Load config
    config = load_config()

    # Init database
    db = JobDatabase()

    # Stats mode
    if args.stats:
        stats = db.get_stats()
        print(f"\n📊 Total jobs tracked: {stats['total_jobs_tracked']}")
        print("\nPar entreprise:")
        for company, count in stats["by_company"]:
            print(f"  {company}: {count}")
        return

    # Init Telegram
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.error("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env")
        sys.exit(1)

    notifier = TelegramNotifier(token, chat_id)

    # Test mode
    if args.test:
        print("Testing Telegram connection...")
        if notifier.test_connection():
            print("✅ Message sent! Check your Telegram.")
        else:
            print("❌ Failed to send message. Check your token and chat_id.")
        return

    # Init engine
    silent = args.seed or args.no_notify
    engine = JobEngine(config, db, notifier, silent=silent)

    if args.seed:
        logger.info("SEED MODE: saving all current jobs to DB without notifying...")
        checked, new, errors = engine.run()
        logger.info(f"Seed complete. {new} jobs saved. Future scans will only notify for NEW postings.")
        return

    if args.loop:
        interval = args.loop * 60
        logger.info(f"Running in loop mode every {args.loop} minutes")
        while True:
            try:
                checked, new, errors = engine.run()
                if errors:
                    notifier.send_summary(checked, new, errors)
                logger.info(f"Next scan in {args.loop} minutes...")
                time.sleep(interval)
            except KeyboardInterrupt:
                logger.info("Stopped.")
                break
    else:
        checked, new, errors = engine.run()
        if errors:
            notifier.send_summary(checked, new, errors)
        logger.info(f"Done. {new} new jobs found across {checked} sources.")


if __name__ == "__main__":
    main()
