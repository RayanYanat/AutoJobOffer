import logging
from datetime import datetime, timezone, timedelta
from typing import List
from .base import BaseScraper
from ..models import Job

logger = logging.getLogger(__name__)


class SmartRecruitersScraper(BaseScraper):
    """
    Scraper for companies using SmartRecruiters.

    Public API: GET https://api.smartrecruiters.com/v1/companies/{company_id}/postings

    Config params:
      company_id: e.g. "BNPParibas", "SocieteGenerale"
    """

    API_BASE = "https://api.smartrecruiters.com/v1/companies/{cid}/postings"
    PAGE_SIZE = 100

    def fetch_jobs(self) -> List[Job]:
        cid = self.config["company_id"]
        max_age = self.config.get("max_age_days", 7)
        url = self.API_BASE.format(cid=cid)
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age)

        all_jobs = []
        offset = 0

        while True:
            params = {"limit": self.PAGE_SIZE, "offset": offset}
            if self.keywords:
                params["q"] = " ".join(self.keywords)

            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            content = data.get("content", [])
            if not content:
                break

            for item in content:
                # Filter by date
                released = item.get("releasedDate", "")
                if released:
                    try:
                        dt = datetime.fromisoformat(str(released).replace("Z", "+00:00"))
                        if dt < cutoff:
                            continue
                    except (ValueError, TypeError):
                        pass

                location_parts = []
                loc = item.get("location", {})
                if loc.get("city"):
                    location_parts.append(loc["city"])
                if loc.get("country"):
                    location_parts.append(loc["country"])
                location_str = ", ".join(location_parts) or "Non précisé"

                dept = item.get("department", {}).get("label", "")
                exp = item.get("experienceLevel", {}).get("label", "")

                job = Job(
                    job_id=item.get("id", ""),
                    title=item.get("name", "Unknown"),
                    company=self.company_name,
                    location=location_str,
                    url=item.get("ref", "") or f"https://jobs.smartrecruiters.com/{cid}/{item.get('id', '')}",
                    posted_date=str(item.get("releasedDate", ""))[:10],
                    contract_type=item.get("typeOfEmployment", {}).get("label", ""),
                    seniority=exp,
                    department=dept,
                    source="smartrecruiters",
                )
                all_jobs.append(job)

            total = data.get("totalFound", 0)
            offset += self.PAGE_SIZE
            if offset >= total:
                break

        logger.info(f"[{self.company_name}] SmartRecruiters returned {len(all_jobs)} raw jobs")
        return all_jobs
