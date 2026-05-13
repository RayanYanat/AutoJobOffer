import re
import logging
from typing import List, Optional
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
        max_age = self.config.get("max_age_days", 7)

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
                posted_on = p.get("postedOn", "")

                # Filter by age — skip old postings
                age_days = self._parse_posted_age(posted_on)
                if age_days is not None and age_days > max_age:
                    continue

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
                    posted_date=posted_on,
                    contract_type=self._extract_field(p, "time"),
                    seniority=self._extract_field(p, "level"),
                    source="workday",
                )
                all_jobs.append(job)

            total = data.get("total", 0)
            offset += self.PAGE_SIZE
            if offset >= total:
                break

        logger.info(f"[{self.company_name}] Workday returned {len(all_jobs)} jobs (max {max_age} days old)")
        return all_jobs

    @staticmethod
    def _parse_posted_age(posted_on: str) -> Optional[int]:
        """
        Parse Workday's 'postedOn' field into number of days.
        Handles both English and French formats.

        EN: "Posted Today", "Posted Yesterday", "Posted 3 Days Ago", "Posted 30+ Days Ago"
        FR: "Offre publiée aujourd'hui", "Offre publiée hier", "Offre publiée il y a 2 jours",
            "Offre publiée il y a 30 jours ou plus"
        """
        if not posted_on:
            return None
        text = posted_on.lower()
        if "today" in text or "aujourd" in text:
            return 0
        if "yesterday" in text or "hier" in text:
            return 1
        # "30+ Days Ago" or "il y a 30 jours ou plus"
        if "ou plus" in text or "30+" in text:
            return 31
        # "3 Days Ago" or "il y a 3 jours"
        match = re.search(r"(\d+)\+?\s*(?:days?\s*ago|jours?)", text)
        if match:
            return int(match.group(1))
        return None  # Unknown format — don't filter it out

    @staticmethod
    def _extract_field(posting: dict, hint: str) -> str:
        """Extract a field from bulletFields by keyword hint."""
        for field in posting.get("bulletFields", []):
            if isinstance(field, str) and hint.lower() in field.lower():
                return field
        return ""
