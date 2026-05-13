#!/usr/bin/env python3
"""
Verify that all configured sources are reachable.
Run this after setup to identify which URLs need fixing.

Usage: python verify_sources.py
"""

import yaml
import requests
import sys

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )
}


def check_workday(company: dict) -> tuple[bool, str]:
    base_url = company.get("base_url", "")
    slug = company.get("company_slug", "")
    site = company.get("site", "")
    url = f"https://{base_url}/wday/cxs/{slug}/{site}/jobs"
    try:
        resp = requests.post(
            url,
            json={"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""},
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code == 200 and "jobPostings" in resp.json():
            total = resp.json().get("total", 0)
            return True, f"OK ({total} jobs)"
        return False, f"HTTP {resp.status_code} — response doesn't match Workday format"
    except Exception as e:
        return False, str(e)


def check_greenhouse(company: dict) -> tuple[bool, str]:
    slug = company.get("board_slug", "")
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200 and "jobs" in resp.json():
            total = len(resp.json()["jobs"])
            return True, f"OK ({total} jobs)"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)


def check_smartrecruiters(company: dict) -> tuple[bool, str]:
    cid = company.get("company_id", "")
    url = f"https://api.smartrecruiters.com/v1/companies/{cid}/postings"
    try:
        resp = requests.get(url, params={"limit": 1}, headers=HEADERS, timeout=10)
        if resp.status_code == 200 and "content" in resp.json():
            total = resp.json().get("totalFound", 0)
            return True, f"OK ({total} jobs)"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)


def check_lever(company: dict) -> tuple[bool, str]:
    slug = company.get("company_slug", "")
    url = f"https://api.lever.co/v0/postings/{slug}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200 and isinstance(resp.json(), list):
            total = len(resp.json())
            return True, f"OK ({total} jobs)"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)


def check_careers_page(company: dict) -> tuple[bool, str]:
    url = company.get("careers_url", "")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        if resp.status_code == 200:
            return True, f"OK (page loads, {len(resp.text)} chars)"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)


def check_oracle_hcm(company: dict) -> tuple[bool, str]:
    base_url = company.get("base_url", "")
    site_id = company.get("site_id", "CX_1001")
    url = f"https://{base_url}/hcmUI/CandidateExperience/en/sites/{site_id}/requisitions"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        if resp.status_code == 200:
            return True, f"OK (page loads, {len(resp.text)} chars)"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)


CHECKERS = {
    "workday": check_workday,
    "greenhouse": check_greenhouse,
    "smartrecruiters": check_smartrecruiters,
    "lever": check_lever,
    "careers_page": check_careers_page,
    "oracle_hcm": check_oracle_hcm,
}


def main():
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    companies = config.get("companies", [])
    ok_count = 0
    fail_count = 0
    skip_count = 0

    print(f"\nVerifying {len(companies)} sources...\n")
    print(f"{'Company':<35} {'Scraper':<18} {'Status'}")
    print("=" * 90)

    for company in companies:
        name = company["name"]
        scraper = company.get("scraper", "unknown")
        enabled = company.get("enabled", True)

        if not enabled:
            print(f"{name:<35} {scraper:<18} ⏭️  DISABLED")
            skip_count += 1
            continue

        checker = CHECKERS.get(scraper)
        if not checker:
            print(f"{name:<35} {scraper:<18} ❓ Unknown scraper type")
            fail_count += 1
            continue

        success, msg = checker(company)
        if success:
            print(f"{name:<35} {scraper:<18} ✅ {msg}")
            ok_count += 1
        else:
            print(f"{name:<35} {scraper:<18} ❌ {msg}")
            fail_count += 1

    print(f"\n{'=' * 90}")
    print(f"✅ {ok_count} OK  |  ❌ {fail_count} FAILED  |  ⏭️  {skip_count} DISABLED")
    print(f"\nFix failed sources in config.yaml, then re-run this script.")

    sys.exit(1 if fail_count > 0 else 0)


if __name__ == "__main__":
    main()
