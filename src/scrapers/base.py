import hashlib
import logging
import requests
from abc import ABC, abstractmethod
from typing import List, Optional
from ..models import Job

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all job scrapers."""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/html, */*",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    }

    def __init__(self, company_name: str, config: dict):
        self.company_name = company_name
        self.config = config
        self.keywords: List[str] = config.get("keywords", [])
        self.locations: List[str] = config.get("locations", [])
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    @abstractmethod
    def fetch_jobs(self) -> List[Job]:
        """Fetch all matching jobs from the source. Must be implemented by subclasses."""
        pass

    def scrape(self) -> List[Job]:
        """Run the scraper with error handling."""
        try:
            jobs = self.fetch_jobs()
            jobs = self._filter_jobs(jobs)
            logger.info(f"[{self.company_name}] Found {len(jobs)} matching jobs")
            return jobs
        except requests.exceptions.Timeout:
            logger.warning(f"[{self.company_name}] Request timed out")
            return []
        except requests.exceptions.ConnectionError:
            logger.warning(f"[{self.company_name}] Connection error")
            return []
        except Exception as e:
            logger.error(f"[{self.company_name}] Scraping failed: {e}")
            return []

    def _filter_jobs(self, jobs: List[Job]) -> List[Job]:
        """Filter jobs by keywords and location."""
        filtered = jobs

        if self.keywords:
            filtered = [
                j for j in filtered
                if any(
                    kw.lower() in j.title.lower()
                    or kw.lower() in (j.department or "").lower()
                    for kw in self.keywords
                )
            ]

        if self.locations:
            filtered = [
                j for j in filtered
                if any(
                    loc.lower() in j.location.lower()
                    for loc in self.locations
                )
            ]

        return filtered

    @staticmethod
    def generate_id(company: str, title: str, location: str) -> str:
        """Generate a unique job ID from key fields."""
        raw = f"{company}|{title}|{location}".lower().strip()
        return hashlib.md5(raw.encode()).hexdigest()[:16]
