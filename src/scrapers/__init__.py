from .workday import WorkdayScraper
from .greenhouse import GreenhouseScraper
from .smartrecruiters import SmartRecruitersScraper
from .lever import LeverScraper
from .careers_page import CareersPageScraper
from .oracle_hcm import OracleHCMScraper

SCRAPER_MAP = {
    "workday": WorkdayScraper,
    "greenhouse": GreenhouseScraper,
    "smartrecruiters": SmartRecruitersScraper,
    "lever": LeverScraper,
    "careers_page": CareersPageScraper,
    "oracle_hcm": OracleHCMScraper,
}
