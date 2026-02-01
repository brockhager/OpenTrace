import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Optional

import httpx
from bs4 import BeautifulSoup


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

        # Extract basic info (avoid sensitive fields like dental records, DNA)
        data = {
            'pfif_id': f'opentrace.org/person.namus.{case_id}',
            'source_url': f"{self.BASE_URL}/case/{case_id}",
            'author_name': 'NamUs',
            'profile_url': f"{self.BASE_URL}/case/{case_id}"
        }

        # Name (if available)
        name_elem = soup.find('h1', class_='case-name')
        if name_elem:
            data['full_name'] = name_elem.get_text(strip=True)

        # Age
        age_elem = soup.find(text='Age:').find_next('td') if soup.find(text='Age:') else None
        if age_elem:
            try:
                data['age'] = int(age_elem.get_text(strip=True))
            except ValueError:
                pass

        # Sex
        sex_elem = soup.find(text='Sex:').find_next('td') if soup.find(text='Sex:') else None
        if sex_elem:
            data['sex'] = sex_elem.get_text(strip=True)

        # Last seen location (circumstantial)
        location_elem = soup.find(text='Circumstances of Disappearance').find_next('p') if soup.find(text='Circumstances of Disappearance') else None
        if location_elem:
            data['last_seen_location'] = location_elem.get_text(strip=True)[:200]  # Truncate

        # Photos (URLs only, no download)
        photo_urls = []
        for img in soup.find_all('img', class_='case-photo'):
            src = img.get('src')
            if src and src.startswith('/'):
                photo_urls.append(f"{self.BASE_URL}{src}")
        if photo_urls:
            data['photo_urls'] = photo_urls

        return data if data.get('full_name') or data.get('age') else None

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


async def main():
    """Example usage."""
    case_ids = ["MP12345", "MP67890"]  # Example case IDs

    async with NamUsScraper() as scraper:
        results = await scraper.scrape_multiple(case_ids)

        for result in results:
            print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())