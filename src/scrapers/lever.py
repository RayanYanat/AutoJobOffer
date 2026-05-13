import logging
from typing import List
from .base import BaseScraper
from ..models import Job

logger = logging.getLogger(__name__)


class LeverScraper(BaseScraper):
    """
    Scraper for companies using Lever ATS.

    Public API: GET https://api.lever.co/v0/postings/{company_slug}

    Config params:
      company_slug: e.g. "moelis", "ardian"
    """

    API_BASE = "https://api.lever.co/v0/postings/{slug}"

    def fetch_jobs(self) -> List[Job]:
        slug = self.config["company_slug"]
        url = self.API_BASE.format(slug=slug)

        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        jobs = []
        for item in data:
            location_str = item.get("categories", {}).get("location", "Non précisé")
            department = item.get("categories", {}).get("department", "")
            team = item.get("categories", {}).get("team", "")
            commitment = item.get("categories", {}).get("commitment", "")

            job = Job(
                job_id=item.get("id", ""),
                title=item.get("text", "Unknown"),
                company=self.company_name,
                location=location_str,
                url=item.get("hostedUrl", "") or item.get("applyUrl", ""),
                posted_date=self._ts_to_date(item.get("createdAt")),
                contract_type=commitment,
                department=f"{department} - {team}" if team else department,
                source="lever",
            )
            jobs.append(job)

        logger.info(f"[{self.company_name}] Lever returned {len(jobs)} raw jobs")
        return jobs

    @staticmethod
    def _ts_to_date(timestamp_ms) -> str:
        if not timestamp_ms:
            return ""
        import datetime
        dt = datetime.datetime.fromtimestamp(timestamp_ms / 1000)
        return dt.strftime("%Y-%m-%d")
