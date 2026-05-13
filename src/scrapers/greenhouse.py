import logging
from datetime import datetime, timezone, timedelta
from typing import List
from .base import BaseScraper
from ..models import Job

logger = logging.getLogger(__name__)


class GreenhouseScraper(BaseScraper):
    """
    Scraper for companies using Greenhouse ATS.

    Public API: GET https://boards-api.greenhouse.io/v1/boards/{board_slug}/jobs

    Config params:
      board_slug: e.g. "blackrock", "evercore"
    """

    API_BASE = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"

    def fetch_jobs(self) -> List[Job]:
        slug = self.config["board_slug"]
        max_age = self.config.get("max_age_days", 7)
        url = self.API_BASE.format(slug=slug)

        resp = self.session.get(url, params={"content": "true"}, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age)

        jobs = []
        for item in data.get("jobs", []):
            # Filter by date
            updated = item.get("updated_at", "")
            if updated:
                try:
                    dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    if dt < cutoff:
                        continue
                except (ValueError, TypeError):
                    pass
            location_name = ""
            if item.get("location"):
                location_name = item["location"].get("name", "")

            departments = ", ".join(
                d.get("name", "") for d in item.get("departments", [])
            )

            job = Job(
                job_id=str(item.get("id", "")),
                title=item.get("title", "Unknown"),
                company=self.company_name,
                location=location_name,
                url=item.get("absolute_url", ""),
                posted_date=self._format_date(item.get("updated_at", "")),
                department=departments,
                source="greenhouse",
            )
            jobs.append(job)

        logger.info(f"[{self.company_name}] Greenhouse returned {len(jobs)} raw jobs")
        return jobs

    @staticmethod
    def _format_date(date_str: str) -> str:
        if not date_str:
            return ""
        return date_str[:10]  # "2024-01-15T..." -> "2024-01-15"
