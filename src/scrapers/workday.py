import logging
from typing import List
from .base import BaseScraper
from ..models import Job

logger = logging.getLogger(__name__)


class WorkdayScraper(BaseScraper):
    """
    Scraper for companies using Workday ATS.

    Workday exposes a JSON API at:
      POST https://{base_url}/wday/cxs/{company}/{site}/jobs

    Config params:
      base_url: e.g. "goldmansachs.wd1.myworkdayjobs.com"
      company:  e.g. "goldmansachs"
      site:     e.g. "GS-Careers" (the career site slug)
    """

    MAX_PAGES = 10  # Safety limit
    PAGE_SIZE = 20

    def fetch_jobs(self) -> List[Job]:
        base_url = self.config["base_url"]
        company_slug = self.config["company_slug"]
        site = self.config["site"]

        api_url = f"https://{base_url}/wday/cxs/{company_slug}/{site}/jobs"

        # Use a broad search term for the API (1-2 keywords max),
        # then filter precisely in Python via _filter_jobs().
        # Sending all keywords concatenated returns 0 results.
        if self.keywords:
            search_text = self.keywords[0]  # Most relevant keyword only
        else:
            search_text = ""

        all_jobs = []
        offset = 0

        for _ in range(self.MAX_PAGES):
            payload = {
                "appliedFacets": {},
                "limit": self.PAGE_SIZE,
                "offset": offset,
                "searchText": search_text,
            }

            resp = self.session.post(api_url, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            postings = data.get("jobPostings", [])
            if not postings:
                break

            for p in postings:
                external_path = p.get("externalPath", "")
                job_url = f"https://{base_url}{external_path}"

                job = Job(
                    job_id=external_path.split("/")[-1] if "/" in external_path else self.generate_id(
                        self.company_name, p.get("title", ""), p.get("locationsText", "")
                    ),
                    title=p.get("title", "Unknown"),
                    company=self.company_name,
                    location=p.get("locationsText", "Unknown"),
                    url=job_url,
                    posted_date=p.get("postedOn", ""),
                    contract_type=self._extract_field(p, "time"),
                    seniority=self._extract_field(p, "level"),
                    source="workday",
                )
                all_jobs.append(job)

            total = data.get("total", 0)
            offset += self.PAGE_SIZE
            if offset >= total:
                break

        logger.info(f"[{self.company_name}] Workday returned {len(all_jobs)} raw jobs")
        return all_jobs

    @staticmethod
    def _extract_field(posting: dict, hint: str) -> str:
        """Extract a field from bulletFields by keyword hint."""
        for field in posting.get("bulletFields", []):
            if isinstance(field, str) and hint.lower() in field.lower():
                return field
        return ""
