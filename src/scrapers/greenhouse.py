import logging
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
        url = self.API_BASE.format(slug=slug)

        resp = self.session.get(url, params={"content": "true"}, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        jobs = []
        for item in data.get("jobs", []):
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
