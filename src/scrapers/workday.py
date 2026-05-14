import re
import logging
from typing import List, Optional, Tuple
from .base import BaseScraper
from ..models import Job

logger = logging.getLogger(__name__)

# European countries for matching Location_Country / Country facets
EUROPE_COUNTRIES = [
    "france", "united kingdom", "germany", "switzerland", "netherlands",
    "belgium", "luxembourg", "spain", "italy", "ireland", "portugal",
    "austria", "sweden", "denmark", "norway", "finland", "poland",
    "czech", "monaco", "hungary", "romania", "greece",
]

# European cities / regions for matching Location / locationMainGroup facets
EUROPE_CITIES = [
    "paris", "la défense", "lyon",
    "london", "edinburgh", "glasgow", "manchester", "birmingham", "greater london", "scotland",
    "frankfurt", "berlin", "munich", "münchen", "hamburg", "düsseldorf",
    "geneva", "genève", "zurich", "zürich", "basel", "bern", "lugano",
    "amsterdam", "rotterdam", "den haag", "the hague",
    "brussels", "bruxelles",
    "luxembourg",
    "madrid", "barcelona",
    "milan", "milano", "rome", "roma",
    "dublin",
    "lisbon", "lisboa",
    "vienna", "wien",
    "stockholm", "copenhagen", "oslo", "helsinki",
    "warsaw", "prague", "monaco", "bucharest", "budapest", "athens",
]

# Facet parameter names in priority order (best → fallback)
# Most facets use their facetParameter name as the appliedFacets key,
# except locationMainGroup which must use "locations" as the key.
LOCATION_FACET_PRIORITY = [
    "Location_Country",          # Country-level (Morgan Stanley) — cleanest
    "Country_and_Jurisdiction",  # Country-level (Citi)
    "Country",                   # Country-level (Deutsche Bank)
    "locationMainGroup",         # Grouped/nested (BlackRock, etc.) — key becomes "locations"
    "Location",                  # Office-level (Deutsche Bank fallback)
]

# Map facetParameter → appliedFacets key (only special cases listed)
FACET_KEY_OVERRIDE = {
    "locationMainGroup": "locations",
}


class WorkdayScraper(BaseScraper):
    """
    Scraper for companies using Workday ATS.

    Workday exposes a JSON API at:
      POST https://{base_url}/wday/cxs/{company}/{site}/jobs

    Facet structures vary per instance, so we auto-detect the best
    location facet and use it for API-level European filtering.

    Config params:
      base_url: e.g. "blackrock.wd1.myworkdayjobs.com"
      company_slug:  e.g. "blackrock"
      site:     e.g. "BlackRock_Professional"
    """

    MAX_PAGES = 10
    PAGE_SIZE = 20

    def fetch_jobs(self) -> List[Job]:
        base_url = self.config["base_url"]
        company_slug = self.config["company_slug"]
        site = self.config["site"]
        max_age = self.config.get("max_age_days", 7)
        filter_europe = bool(self.locations)

        api_url = f"https://{base_url}/wday/cxs/{company_slug}/{site}/jobs"

        if self.keywords:
            search_text = self.keywords[0]
        else:
            search_text = ""

        # Step 1: Get European location facet IDs if location filtering is enabled
        applied_facets = {}
        if filter_europe:
            facet_key, euro_ids = self._get_european_location_ids(api_url)
            if euro_ids:
                applied_facets[facet_key] = euro_ids
                # Skip Python-side location filter since API already filters by Europe
                self.skip_location_filter = True
                logger.info(
                    f"[{self.company_name}] Filtering by {len(euro_ids)} European locations "
                    f"(facet: {facet_key})"
                )
            else:
                logger.info(f"[{self.company_name}] No European location facets found, fetching all locations")

        # Step 2: Fetch jobs with facets applied
        all_jobs = []
        offset = 0

        for _ in range(self.MAX_PAGES):
            payload = {
                "appliedFacets": applied_facets,
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

                # Filter by age
                age_days = self._parse_posted_age(posted_on)
                if age_days is not None and age_days > max_age:
                    continue

                external_path = p.get("externalPath", "")
                job_url = f"https://{base_url}/en-US/{site}{external_path}"

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

        logger.info(
            f"[{self.company_name}] Workday returned {len(all_jobs)} jobs "
            f"(max {max_age}d, Europe={'yes' if filter_europe else 'no'})"
        )
        return all_jobs

    def _get_european_location_ids(self, api_url: str) -> Tuple[str, List[str]]:
        """
        Fetch location facets and return (facet_key, matching_ids) for European locations.

        Workday instances use different facet structures:
          - Location_Country / Country: country-level (best for filtering)
          - locations / locationMainGroup: city-level, often nested
          - Location: office-level (most granular)

        We try each in priority order and use the first one that yields matches.
        """
        try:
            resp = self.session.post(
                api_url,
                json={"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            # Build a map of available facets
            facet_map = {}
            for facet in data.get("facets", []):
                param = facet.get("facetParameter", "")
                if param:
                    facet_map[param] = facet

            # Try each location facet type in priority order
            for facet_param in LOCATION_FACET_PRIORITY:
                if facet_param not in facet_map:
                    continue

                facet = facet_map[facet_param]
                is_country_facet = facet_param in (
                    "Location_Country", "Country_and_Jurisdiction", "Country",
                )
                patterns = EUROPE_COUNTRIES if is_country_facet else EUROPE_CITIES + EUROPE_COUNTRIES

                # Extract all leaf values (handling nested structures)
                all_values = self._extract_leaf_values(facet)

                euro_ids = []
                for val in all_values:
                    descriptor = val.get("descriptor", "").lower()
                    val_id = val.get("id", "")
                    if not val_id:
                        continue
                    if any(pat in descriptor for pat in patterns):
                        euro_ids.append(val_id)

                if euro_ids:
                    # The key for appliedFacets may differ from the facetParameter name
                    applied_key = FACET_KEY_OVERRIDE.get(facet_param, facet_param)
                    logger.debug(
                        f"[{self.company_name}] Found {len(euro_ids)} European IDs "
                        f"in facet '{facet_param}' (applied as '{applied_key}')"
                    )
                    return applied_key, euro_ids

            return "", []

        except Exception as e:
            logger.warning(f"[{self.company_name}] Could not fetch location facets: {e}")
            return "", []

    @staticmethod
    def _extract_leaf_values(facet: dict) -> List[dict]:
        """
        Extract all leaf-level values from a facet, handling various nesting depths.

        Workday facets can be structured as:
          - Flat: facet.values = [{descriptor, id, count}, ...]
          - Nested: facet.values = [{descriptor: "Locations", values: [{descriptor, id}, ...]}]
          - Mixed: some values have sub-values, some don't
        """
        results = []

        for val in facet.get("values", []):
            if not isinstance(val, dict):
                continue

            nested = val.get("values", [])
            if isinstance(nested, list) and nested:
                # This is a parent node — recurse into children
                for child in nested:
                    if isinstance(child, dict):
                        # Check if child also has nested values
                        grandchildren = child.get("values", [])
                        if isinstance(grandchildren, list) and grandchildren:
                            for gc in grandchildren:
                                if isinstance(gc, dict) and gc.get("id"):
                                    results.append(gc)
                        elif child.get("id"):
                            results.append(child)
            elif val.get("id"):
                # This is a leaf node
                results.append(val)

        return results

    @staticmethod
    def _parse_posted_age(posted_on: str) -> Optional[int]:
        """
        Parse Workday's 'postedOn' field into number of days.
        Handles both English and French formats.
        """
        if not posted_on:
            return None
        text = posted_on.lower()
        if "today" in text or "aujourd" in text:
            return 0
        if "yesterday" in text or "hier" in text:
            return 1
        if "ou plus" in text or "30+" in text:
            return 31
        match = re.search(r"(\d+)\+?\s*(?:days?\s*ago|jours?)", text)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def _extract_field(posting: dict, hint: str) -> str:
        """Extract a field from bulletFields by keyword hint."""
        for field in posting.get("bulletFields", []):
            if isinstance(field, str) and hint.lower() in field.lower():
                return field
        return ""
