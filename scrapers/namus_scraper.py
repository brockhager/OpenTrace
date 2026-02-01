import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.person import Person
from db.session import async_session

class NamUsScraper:
    """Scraper for NamUs public case pages. Respects rate limits and caches results."""

    BASE_URL = "https://namus.nij.ojp.gov"
    RATE_LIMIT_DELAY = 5  # seconds between requests

    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": "Opentrace/0.1.0 (https://github.com/brockhager/OpenTrace)"
            },
            follow_redirects=True
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def _get_cache_path(self, case_id: str) -> Path:
        """Get cache file path for a case."""
        return self.cache_dir / f"namus_{case_id}.json"

    def _compute_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    async def _fetch_with_cache(self, url: str, case_id: str) -> Optional[str]:
        """Fetch URL with caching. Returns None if not modified."""
        cache_path = self._get_cache_path(case_id)

        # Check cache
        if cache_path.exists():
            with open(cache_path, 'r') as f:
                cached = json.load(f)
                if cached['url'] == url:
                    # Check if source has changed (simplified - in practice, check ETag/Last-Modified)
                    # For now, assume cache is valid for 24 hours
                    import time
                    if time.time() - cached['timestamp'] < 86400:
                        return cached['content']

        # Fetch new content
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            content = response.text

            # Cache with hash
            cache_data = {
                'url': url,
                'content': content,
                'hash': self._compute_hash(content),
                'timestamp': int(asyncio.get_event_loop().time())
            }

            with open(cache_path, 'w') as f:
                json.dump(cache_data, f)

            return content

        except httpx.HTTPStatusError as e:
            print(f"HTTP error for {url}: {e}")
            return None
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def _parse_case_page(self, html: str, case_id: str) -> Optional[Dict]:
        """Parse NamUs case page HTML. Extract only public, non-sensitive fields."""
        soup = BeautifulSoup(html, 'lxml')

        # Generate PFIF-compliant ID
        pfif_id = f'opentrace.org/person/namus.{case_id}'
        
        # Initialize Person data
        person_data = {
            'pfif_id': pfif_id,
            'primary_source': 'namus',
            'source_id': case_id,
            'source_url': f"{self.BASE_URL}/case/{case_id}",
            'source_confidence': 'high',  # NamUs is official government source
            'is_confirmed': False,  # Requires moderator approval
            'status': 'missing'
        }

        # Parse name (split into given/family if possible)
        name_elem = soup.find('h1', class_='case-name')
        if name_elem:
            full_name = name_elem.get_text(strip=True)
            # Simple name parsing - could be enhanced
            if ',' in full_name:
                # "Last, First" format
                parts = full_name.split(',', 1)
                person_data['family_name'] = parts[0].strip()
                if len(parts) > 1:
                    person_data['given_name'] = parts[1].strip()
            else:
                # "First Last" format
                parts = full_name.split()
                if len(parts) >= 2:
                    person_data['given_name'] = parts[0]
                    person_data['family_name'] = ' '.join(parts[1:])
                elif len(parts) == 1:
                    person_data['given_name'] = parts[0]

        # Age
        age_elem = soup.find(string='Age:').find_next('td') if soup.find(string='Age:') else None
        if age_elem:
            try:
                person_data['age_at_disappearance'] = int(age_elem.get_text(strip=True))
            except ValueError:
                pass

        # Sex
        sex_elem = soup.find(string='Sex:').find_next('td') if soup.find(string='Sex:') else None
        if sex_elem:
            person_data['sex'] = sex_elem.get_text(strip=True)

        # Date last seen (try to extract from circumstances)
        date_seen_elem = soup.find(string='Date Last Seen:').find_next('td') if soup.find(string='Date Last Seen:') else None
        if date_seen_elem:
            date_str = date_seen_elem.get_text(strip=True)
            try:
                # Try to parse common date formats
                person_data['date_last_seen'] = datetime.strptime(date_str, '%m/%d/%Y')
            except ValueError:
                pass

        # Date reported
        date_reported_elem = soup.find(string='Date Entered:').find_next('td') if soup.find(string='Date Entered:') else None
        if date_reported_elem:
            date_str = date_reported_elem.get_text(strip=True)
            try:
                person_data['date_reported'] = datetime.strptime(date_str, '%m/%d/%Y')
            except ValueError:
                pass

        return person_data if person_data.get('given_name') or person_data.get('family_name') or person_data.get('age_at_disappearance') else None

    async def save_person(self, person_data: Dict) -> bool:
        """Save scraped person data to database, avoiding duplicates."""
        if not person_data:
            return False
            
        async with async_session() as db:
            try:
                # Check if person already exists
                result = await db.execute(
                    select(Person).where(Person.pfif_id == person_data['pfif_id'])
                )
                existing_person = result.scalar_one_or_none()
                
                if existing_person:
                    print(f"Person {person_data['pfif_id']} already exists, skipping")
                    return False
                
                # Create new Person record
                person = Person(**person_data)
                db.add(person)
                await db.commit()
                
                print(f"Created person: {person.pfif_id} - {person.display_name}")
                return True
                
            except Exception as e:
                print(f"Error saving person {person_data.get('pfif_id')}: {e}")
                await db.rollback()
                return False

    async def scrape_and_save_case(self, case_id: str) -> bool:
        """Scrape a single NamUs case and save to database."""
        person_data = await self.scrape_case(case_id)
        if person_data:
            return await self.save_person(person_data)
        return False

    async def scrape_case(self, case_id: str) -> Optional[Dict]:
        """Scrape a single NamUs case."""
        url = f"{self.BASE_URL}/case/{case_id}"

        # Rate limiting
        await asyncio.sleep(self.RATE_LIMIT_DELAY)

        html = await self._fetch_with_cache(url, case_id)
        if not html:
            return None

        return self._parse_case_page(html, case_id)

    async def scrape_multiple(self, case_ids: list[str]) -> list[Dict]:
        """Scrape multiple cases concurrently (with rate limiting)."""
        results = []
        semaphore = asyncio.Semaphore(1)  # Limit concurrent requests

        async def scrape_with_limit(case_id: str):
            async with semaphore:
                result = await self.scrape_case(case_id)
                if result:
                    results.append(result)

        await asyncio.gather(*[scrape_with_limit(cid) for cid in case_ids])
        return results

    async def scrape_and_save_multiple(self, case_ids: list[str]) -> int:
        """Scrape multiple cases and save to database. Returns count of successful saves."""
        saved_count = 0
        semaphore = asyncio.Semaphore(1)  # Limit concurrent requests

        async def scrape_and_save_with_limit(case_id: str):
            nonlocal saved_count
            async with semaphore:
                success = await self.scrape_and_save_case(case_id)
                if success:
                    saved_count += 1

        await asyncio.gather(*[scrape_and_save_with_limit(cid) for cid in case_ids])
        return saved_count


async def main():
    """Example usage."""
    case_ids = ["MP12345", "MP67890"]  # Example case IDs

    async with NamUsScraper() as scraper:
        saved_count = await scraper.scrape_and_save_multiple(case_ids)
        print(f"Successfully saved {saved_count} persons to database")


if __name__ == "__main__":
    asyncio.run(main())