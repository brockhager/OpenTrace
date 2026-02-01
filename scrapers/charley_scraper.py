import asyncio
import hashlib
import os
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import async_session
from api.models import PersonProfile, AuditLog


class CharleyScraper:
    BASE_URL = "https://charleyproject.org"
    CASE_LIST_URL = "https://charleyproject.org/case-files/?page={page}"
    CACHE_DIR = "cache/charley"
    RATE_LIMIT_DELAY = 5  # Respectful delay

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        os.makedirs(self.CACHE_DIR, exist_ok=True)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def fetch_page(self, url: str) -> Optional[str]:
        """Fetch page with caching."""
        cache_key = hashlib.sha256(url.encode()).hexdigest()
        cache_file = os.path.join(self.CACHE_DIR, f"{cache_key}.html")

        # Check cache
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_content = f.read()
            # Check if still valid (simple: assume 7 days)
            # For now, use cached
            return cached_content

        # Fetch
        response = await self.client.get(url)
        response.raise_for_status()
        content = response.text

        # Cache
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(content)

        return content

    def get_case_urls(self, list_html: str) -> List[str]:
        """Extract case URLs from list page."""
        soup = BeautifulSoup(list_html, "lxml")
        case_links = soup.find_all("a", href=re.compile(r"/case/[^/]+/$"))
        urls = [urljoin(self.BASE_URL, link["href"]) for link in case_links]
        return list(set(urls))  # Dedupe

    async def scrape_case(self, url: str) -> Optional[PersonProfile]:
        """Scrape a single case page."""
        html = await self.fetch_page(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "lxml")

        # Extract fields - use selectors, with fallbacks
        name = None
        age = None
        sex = None
        last_seen = None
        date_missing = None

        # Name: often in h1 or specific div
        name_elem = soup.find("h1") or soup.find("div", class_="case-name")
        if name_elem:
            name = name_elem.get_text(strip=True)

        # Age
        age_elem = soup.find(string=re.compile(r"Age.*:")).find_next("td") if soup.find(string=re.compile(r"Age.*:")) else None
        if age_elem:
            age_text = age_elem.get_text(strip=True)
            age_match = re.search(r"\d+", age_text)
            if age_match:
                age = int(age_match.group())

        # Sex
        sex_elem = soup.find(string=re.compile(r"Sex.*:")).find_next("td") if soup.find(string=re.compile(r"Sex.*:")) else None
        if sex_elem:
            sex_text = sex_elem.get_text(strip=True)
            if "male" in sex_text.lower():
                sex = "Male"
            elif "female" in sex_text.lower():
                sex = "Female"

        # Last seen location
        location_elem = soup.find(string=re.compile(r"Last.*seen")).find_next("p") if soup.find(string=re.compile(r"Last.*seen")) else None
        if location_elem:
            last_seen = location_elem.get_text(strip=True)

        # Date missing
        date_elem = soup.find(string=re.compile(r"Missing.*since")).find_next("td") if soup.find(string=re.compile(r"Missing.*since")) else None
        if date_elem:
            date_missing = date_elem.get_text(strip=True)

        if not name:
            return None  # Skip if no name

        # Generate pfif_id from URL slug
        slug = url.split("/")[-2]  # e.g., john-doe
        pfif_id = f"opentrace.org/person.charley.{slug}"

        return PersonProfile(
            pfif_id=pfif_id,
            author_name="Charley Project",
            full_name=name,  # Charley has full name
            age=age,
            sex=sex,
            last_seen_location=last_seen,
            status="missing",
            is_confirmed=False,  # Requires admin review
            source_date=date_missing,
            profile_url=url,
            source_url=url
        )

    async def ingest_case(self, db: AsyncSession, url: str) -> bool:
        """Ingest a single case. Return True if new."""
        profile = await self.scrape_case(url)
        if not profile:
            return False

        # Check if exists
        existing = await db.execute(select(PersonProfile).where(PersonProfile.pfif_id == profile.pfif_id))
        if existing.scalar_one_or_none():
            return False

        db.add(profile)
        return True

    async def ingest_pages(self, db: AsyncSession, max_pages: int = 10) -> Dict[str, Any]:
        """Ingest cases from multiple list pages."""
        total_ingested = 0
        all_case_urls = set()

        for page in range(1, max_pages + 1):
            list_url = self.CASE_LIST_URL.format(page=page)
            list_html = await self.fetch_page(list_url)
            if not list_html:
                break

            case_urls = self.get_case_urls(list_html)
            all_case_urls.update(case_urls)

            # Rate limit
            await asyncio.sleep(self.RATE_LIMIT_DELAY)

        # Now ingest cases
        for url in all_case_urls:
            new = await self.ingest_case(db, url)
            if new:
                total_ingested += 1
            await asyncio.sleep(self.RATE_LIMIT_DELAY)

        await db.commit()

        # Audit log
        audit = AuditLog(
            action="ingest_charley",
            actor_id="system",
            details={"total_ingested": total_ingested, "pages_scraped": page}
        )
        db.add(audit)
        await db.commit()

        return {"total_ingested": total_ingested, "pages_scraped": page}