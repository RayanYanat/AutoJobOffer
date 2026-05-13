import time
import logging
from typing import List, Tuple
from .database import JobDatabase
from .notifier import TelegramNotifier
from .models import Job
from .scrapers import SCRAPER_MAP

logger = logging.getLogger(__name__)


class JobEngine:
    """Main orchestration engine — runs all scrapers, deduplicates, notifies."""

    def __init__(self, config: dict, db: JobDatabase, notifier: TelegramNotifier, silent: bool = False):
        self.config = config
        self.db = db
        self.notifier = notifier
        self.silent = silent  # If True, don't send notifications (seed mode)
        self.global_keywords = config.get("keywords", [])
        self.global_locations = config.get("locations", [])
        self.global_max_age = config.get("max_age_days", 7)
        self.delay_between_sources = config.get("delay_between_sources", 2)

    def run(self) -> Tuple[int, int, List[str]]:
        """
        Run a full scraping cycle.
        Returns: (total_sources_checked, total_new_jobs, errors)
        """
        companies = self.config.get("companies", [])
        total_new = 0
        total_checked = 0
        errors = []

        logger.info(f"Starting scan of {len(companies)} companies...")

        for company_cfg in companies:
            name = company_cfg["name"]
            scraper_type = company_cfg.get("scraper")

            if not scraper_type or scraper_type not in SCRAPER_MAP:
                logger.warning(f"[{name}] Unknown scraper type: {scraper_type}, skipping")
                continue

            if not company_cfg.get("enabled", True):
                logger.debug(f"[{name}] Disabled, skipping")
                continue

            try:
                # Merge global config with company-specific config
                scraper_config = {**company_cfg}
                if not scraper_config.get("keywords"):
                    scraper_config["keywords"] = self.global_keywords
                if not scraper_config.get("locations"):
                    scraper_config["locations"] = self.global_locations
                if "max_age_days" not in scraper_config:
                    scraper_config["max_age_days"] = self.global_max_age

                # Instantiate and run scraper
                scraper_cls = SCRAPER_MAP[scraper_type]
                scraper = scraper_cls(name, scraper_config)
                jobs = scraper.scrape()

                # Filter new jobs
                new_jobs = self.db.filter_new_jobs(jobs)

                # Log scrape
                self.db.log_scrape(
                    source=scraper_type,
                    company=name,
                    jobs_found=len(jobs),
                    new_jobs=len(new_jobs),
                )

                if new_jobs:
                    logger.info(f"[{name}] {len(new_jobs)} NEW jobs found!")
                    if not self.silent:
                        self.notifier.send_new_jobs(new_jobs)
                    self.db.mark_as_seen(new_jobs)
                    total_new += len(new_jobs)
                else:
                    logger.info(f"[{name}] No new jobs")

                total_checked += 1

            except Exception as e:
                error_msg = f"{name}: {str(e)}"
                logger.error(f"[{name}] Error: {e}")
                errors.append(error_msg)
                self.db.log_scrape(
                    source=scraper_type,
                    company=name,
                    jobs_found=0,
                    new_jobs=0,
                    error=str(e),
                )

            # Respect rate limits between sources
            time.sleep(self.delay_between_sources)

        logger.info(
            f"Scan complete: {total_checked} sources, {total_new} new jobs, {len(errors)} errors"
        )

        return total_checked, total_new, errors
