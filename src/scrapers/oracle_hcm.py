import logging
from typing import List
from .base import BaseScraper
from ..models import Job

logger = logging.getLogger(__name__)


class OracleHCMScraper(BaseScraper):
    """
    Scraper for companies using Oracle HCM Cloud (used by JPMorgan, etc.).

    API endpoint:
      GET https://{base_url}/hcmRestApi/resources/latest/recruitingCEJobRequisitions

    Config params:
      base_url: e.g. "jpmc.fa.oraclecloud.com"
      site_id:  e.g. "CX_1001"
    """

    PAGE_SIZE = 25
    MAX_PAGES = 10

    def fetch_jobs(self) -> List[Job]:
        base_url = self.config["base_url"]
        site_id = self.config.get("site_id", "CX_1001")

        search_text = " ".join(self.keywords) if self.keywords else "analyst"

        # Oracle HCM REST API for job requisitions
        api_url = f"https://{base_url}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"

        all_jobs = []
        offset = 0

        for _ in range(self.MAX_PAGES):
            params = {
                "onlyData": "true",
                "expand": "requisitionList.secondaryLocations,flexFieldsFacet.values",
                "finder": f"findReqs;siteNumber={site_id},keyword={search_text},limit={self.PAGE_SIZE},offset={offset}",
            }

            resp = self.session.get(api_url, params=params, timeout=20)

            # Oracle HCM might return 404 or different structure
            # Fall back to the UI search API
            if resp.status_code != 200:
                return self._fallback_scrape(base_url, site_id, search_text)

            data = resp.json()
            items = data.get("items", [])
            if not items:
                # Try nested structure
                items = data.get("items", [{}])[0].get("requisitionList", []) if data.get("items") else []

            if not items:
                break

            for item in items:
                title = item.get("Title", item.get("title", "Unknown"))
                location = item.get("PrimaryLocation", item.get("primaryLocation", "Unknown"))
                req_id = str(item.get("Id", item.get("id", "")))
                posting_date = item.get("PostedDate", item.get("postedDate", ""))

                job_url = (
                    f"https://{base_url}/hcmUI/CandidateExperience/en/sites/{site_id}"
                    f"/job/{req_id}"
                )

                job = Job(
                    job_id=req_id or self.generate_id(self.company_name, title, location),
                    title=title,
                    company=self.company_name,
                    location=location,
                    url=job_url,
                    posted_date=str(posting_date)[:10] if posting_date else "",
                    source="oracle_hcm",
                )
                all_jobs.append(job)

            offset += self.PAGE_SIZE
            total = data.get("totalCount", data.get("count", 0))
            if offset >= total or not items:
                break

        logger.info(f"[{self.company_name}] Oracle HCM returned {len(all_jobs)} raw jobs")
        return all_jobs

    def _fallback_scrape(self, base_url: str, site_id: str, search_text: str) -> List[Job]:
        """Fallback: scrape the candidate experience UI search page."""
        logger.info(f"[{self.company_name}] Oracle REST API unavailable, trying UI endpoint")

        ui_url = (
            f"https://{base_url}/hcmUI/CandidateExperience/en/sites/{site_id}/requisitions"
        )
        params = {"keyword": search_text, "sortBy": "POSTING_DATES_ORDER"}

        try:
            resp = self.session.get(ui_url, params=params, timeout=15)
            resp.raise_for_status()

            # The UI page may contain JSON data in a script tag or load via XHR
            # For now, return empty and log — this needs manual investigation per site
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "lxml")

            # Try to find job links in the page
            jobs = []
            for link in soup.select("a[href*='job/'], a[href*='requisition']"):
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if title and len(title) > 5 and href:
                    full_url = f"https://{base_url}{href}" if href.startswith("/") else href
                    jobs.append(Job(
                        job_id=self.generate_id(self.company_name, title, full_url),
                        title=title,
                        company=self.company_name,
                        location="See posting",
                        url=full_url,
                        source="oracle_hcm_fallback",
                    ))

            logger.info(f"[{self.company_name}] Oracle HCM fallback found {len(jobs)} jobs")
            return jobs

        except Exception as e:
            logger.error(f"[{self.company_name}] Oracle HCM fallback failed: {e}")
            return []
