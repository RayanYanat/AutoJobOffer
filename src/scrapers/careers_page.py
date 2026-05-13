import logging
import re
from typing import List
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .base import BaseScraper
from ..models import Job

logger = logging.getLogger(__name__)


class CareersPageScraper(BaseScraper):
    """
    Generic scraper for career pages using HTML parsing.

    This is the fallback scraper for companies without a known ATS API.
    It tries to find job listings from the HTML of the career page.

    Config params:
      careers_url:    e.g. "https://careers.example.com/search"
      link_selector:  CSS selector for job links (default: "a[href*='job'], a[href*='career'], a[href*='offre']")
      title_selector: CSS selector for job title within each link (optional)
      params:         dict of query params to add to the URL (optional)
    """

    DEFAULT_LINK_SELECTORS = [
        "a[href*='job']",
        "a[href*='offre']",
        "a[href*='career']",
        "a[href*='poste']",
        "a[href*='position']",
        "a[href*='vacancy']",
        "a[href*='opening']",
    ]

    def fetch_jobs(self) -> List[Job]:
        careers_url = self.config["careers_url"]
        params = self.config.get("params", {})
        link_selector = self.config.get("link_selector", "")

        # Inject keyword search if the URL supports it
        if self.keywords and "search_param" in self.config:
            params[self.config["search_param"]] = " ".join(self.keywords)

        resp = self.session.get(careers_url, params=params, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")

        # Try custom selector first, then fallback to defaults
        if link_selector:
            selectors = [link_selector]
        else:
            selectors = self.DEFAULT_LINK_SELECTORS

        seen_urls = set()
        jobs = []

        for selector in selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get("href", "")
                if not href or href == "#":
                    continue

                full_url = urljoin(careers_url, href)
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                title = self._extract_title(link)
                if not title or len(title) < 5:
                    continue

                # Skip navigation/generic links
                if self._is_navigation_link(title):
                    continue

                location = self._extract_location(link)

                job = Job(
                    job_id=self.generate_id(self.company_name, title, full_url),
                    title=title,
                    company=self.company_name,
                    location=location,
                    url=full_url,
                    source="careers_page",
                )
                jobs.append(job)

        logger.info(f"[{self.company_name}] HTML scraper found {len(jobs)} raw jobs")
        return jobs

    def _extract_title(self, link_element) -> str:
        """Extract clean job title from a link element."""
        title_selector = self.config.get("title_selector", "")
        if title_selector:
            title_el = link_element.select_one(title_selector)
            if title_el:
                return title_el.get_text(strip=True)
        return link_element.get_text(strip=True)

    def _extract_location(self, link_element) -> str:
        """Try to find location info near the link."""
        parent = link_element.parent
        if parent:
            loc_patterns = [
                r"(Paris|Lyon|London|Geneva|Frankfurt|Madrid|Milan|Amsterdam|Brussels|Zurich)",
                r"(France|UK|Switzerland|Germany|Spain|Italy|Netherlands|Belgium)",
            ]
            text = parent.get_text()
            for pattern in loc_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1)
        return "Non précisé"

    @staticmethod
    def _is_navigation_link(title: str) -> bool:
        """Filter out navigation links."""
        skip_words = [
            "login", "sign in", "register", "submit", "apply",
            "home", "contact", "about", "privacy", "cookie",
            "back", "next", "previous", "menu", "search",
        ]
        title_lower = title.lower().strip()
        return any(title_lower == w or title_lower.startswith(w + " ") for w in skip_words)
