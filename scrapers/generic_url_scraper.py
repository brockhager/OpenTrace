import asyncio
import hashlib
import json
import re
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.person import Person
from models.event import Event
from models.location import Location
from db.session import async_session


class GenericUrlScraper:
    """
    Generic scraper for missing persons data from arbitrary URLs.
    Supports common missing persons websites and extracts Person, Event, and Location data.
    """

    RATE_LIMIT_DELAY = 5  # seconds between requests

    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": "Opentrace/0.1.0 (https://github.com/brockhager/OpenTrace)"
            },
            follow_redirects=True,
            timeout=30
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def _get_cache_path(self, url_hash: str) -> Path:
        """Get cache file path based on URL hash."""
        return self.cache_dir / f"generic_{url_hash}.json"

    def _compute_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    async def _fetch_with_cache(self, url: str) -> Optional[str]:
        """Fetch URL with caching. Returns None if not modified."""
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:8]
        cache_path = self._get_cache_path(url_hash)

        # Check cache (24-hour TTL)
        if cache_path.exists():
            with open(cache_path, 'r') as f:
                try:
                    cached = json.load(f)
                    import time
                    if time.time() - cached.get('timestamp', 0) < 86400:
                        return cached.get('content')
                except (json.JSONDecodeError, KeyError):
                    pass

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

    def _extract_text_between(self, html: str, start: str, end: str) -> Optional[str]:
        """Extract text between two markers."""
        try:
            start_idx = html.find(start)
            if start_idx == -1:
                return None
            start_idx += len(start)
            end_idx = html.find(end, start_idx)
            if end_idx == -1:
                return None
            return html[start_idx:end_idx].strip()
        except Exception:
            return None

    def _parse_generic_page(self, html: str, url: str) -> Optional[Dict]:
        """
        Parse a generic missing persons page.
        Attempts to extract person, location, and event data using common patterns.
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Generate PFIF ID from URL
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:8]
        pfif_id = f'opentrace.org/person/generic.{url_hash}'

        person_data = {
            'pfif_id': pfif_id,
            'primary_source': 'custom_url',
            'source_url': url,
            'source_confidence': 'medium',  # Custom URLs are less trusted
            'is_confirmed': False,  # Requires moderator approval
            'status': 'missing'
        }

        # Extract basic text content
        text_content = soup.get_text(separator=' ')

        # Try to extract name from meta tags first (og:title, twitter:title), then title tag
        full_name = None
        og_title = soup.find('meta', property='og:title') or soup.find('meta', attrs={'name':'og:title'})
        if og_title and og_title.get('content'):
            full_name = og_title['content'].strip()
        if not full_name:
            tw_title = soup.find('meta', attrs={'name':'twitter:title'})
            if tw_title and tw_title.get('content'):
                full_name = tw_title['content'].strip()
        if not full_name:
            if soup.title and soup.title.string:
                # Heuristic: titles often have "Missing Person - John Doe" or "John Doe | Site"
                title_text = soup.title.string.strip()
                # use last segment after common separators
                for sep in ['|', '-', '—', ':']:
                    if sep in title_text:
                        candidate = title_text.split(sep)[-1].strip()
                        if 3 < len(candidate) < 100:
                            full_name = candidate
                            break
                if not full_name and 3 < len(title_text) < 100:
                    full_name = title_text

        # Try to find names (look for common patterns)
        # Pattern: "Missing Person: John Doe" or "Name: John Doe" or all-caps formats
        name_patterns = [
            r'(?:missing\s+person|name|missing)?:?\s*([A-Z][a-zA-Z\'"\-]+(?:\s+[A-Z][a-zA-Z\'"\-]+)*)',
            r'(?:looking\s+for|find|locate)\s*:?\s*([A-Z][a-zA-Z\'"\-]+(?:\s+[A-Z][a-zA-Z\'"\-]+)*)',
            r'([A-Z]{2,}(?:\s+[A-Z]{2,})+)'  # ALL CAPS NAME
        ]

        if not full_name:
            for pattern in name_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    candidate = match.group(1).strip()
                    # If ALL CAPS, convert to Title Case and handle "DOE, JOHN" -> "John Doe"
                    if candidate.isupper():
                        candidate = candidate.title()
                        if ',' in candidate:
                            parts = [p.strip() for p in candidate.split(',')]
                            if len(parts) >= 2:
                                candidate = f"{parts[1]} {parts[0]}"
                    full_name = candidate
                    break

        # If no pattern match, try to find h1 or h2 tags
        if not full_name:
            for tag in soup.find_all(['h1', 'h2']):
                tag_text = tag.get_text(strip=True)
                # Filter out navigation and common header text
                if any(x in tag_text.lower() for x in ['admin', 'menu', 'nav', 'header', 'search']):
                    continue
                if 3 < len(tag_text) < 100:
                    full_name = tag_text
                    break

        if full_name:
            # Clean up common prefixes/suffixes
            full_name = re.sub(r'^(missing person[:\-\s]+)', '', full_name, flags=re.IGNORECASE).strip()
            full_name = re.sub(r'(\s+\|\s+.*)$', '', full_name).strip()
            # Try to parse name into given/family
            # Handle "Last, First" format
            if ',' in full_name:
                parts = [p.strip() for p in full_name.split(',')]
                if len(parts) >= 2:
                    person_data['given_name'] = parts[1]
                    person_data['family_name'] = parts[0]
                else:
                    person_data['given_name'] = full_name
            else:
                parts = full_name.split()
                if len(parts) >= 2:
                    person_data['given_name'] = parts[0]
                    person_data['family_name'] = ' '.join(parts[1:])
                elif len(parts) == 1:
                    person_data['given_name'] = parts[0]
        # Extract age (pattern: "Age: 25" or "age 25 years" or "25 years old")
        age_match = re.search(r'age\s*:?\s*(\d+)', text_content, re.IGNORECASE)
        if not age_match:
            age_match = re.search(r'(\d{1,3})\s+years\s+old', text_content, re.IGNORECASE)
        if age_match:
            try:
                person_data['age_at_disappearance'] = int(age_match.group(1))
            except ValueError:
                pass

        # Extract sex/gender (pattern: "Sex: Male" or "Gender: Female")
        sex_match = re.search(r'(?:sex|gender)\s*:?\s*(male|female|unknown)', text_content, re.IGNORECASE)
        if sex_match:
            person_data['sex'] = sex_match.group(1).capitalize()

        # Extract dates (pattern: "Last Seen: MM/DD/YYYY" or "Missing Since: Date")
        date_patterns = [
            (r'last\s+seen\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})', '%m/%d/%Y'),
            (r'missing\s+since\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})', '%m/%d/%Y'),
            (r'disappeared\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})', '%m/%d/%Y'),
            (r'last\s+seen\s*:?\s*(\d{4}-\d{1,2}-\d{1,2})', '%Y-%m-%d'),
        ]

        for pattern, date_format in date_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                try:
                    person_data['date_last_seen'] = datetime.strptime(match.group(1), date_format).date()
                    break
                except ValueError:
                    continue

        # Only return if we found at least a name or age
        if not (person_data.get('given_name') or person_data.get('family_name') or person_data.get('age_at_disappearance')):
            return None

        return person_data

    async def save_person(self, person_data: Dict) -> bool:
        """Save scraped person data to database, avoiding duplicates."""
        if not person_data:
            return False

        async with async_session() as db:
            try:
                # Check if person already exists (by PFIF ID or source_url)
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

    async def scrape_and_save_url(self, url: str) -> Optional[Dict]:
        """Scrape a URL and save to database if valid data found."""
        # Rate limiting
        await asyncio.sleep(self.RATE_LIMIT_DELAY)

        html = await self._fetch_with_cache(url)
        if not html:
            return None

        person_data = self._parse_generic_page(html, url)
        if not person_data:
            return None

        # Save to database
        created = await self.save_person(person_data)
        person_data['created'] = created

        return person_data

    async def scrape_url_only(self, url: str) -> Optional[Dict]:
        """Scrape URL without saving (for preview)."""
        # Rate limiting
        await asyncio.sleep(self.RATE_LIMIT_DELAY)

        html = await self._fetch_with_cache(url)
        if not html:
            return None

        return self._parse_generic_page(html, url)


async def main():
    """Example usage."""
    test_url = "https://example.com/missing-person"

    async with GenericUrlScraper() as scraper:
        result = await scraper.scrape_and_save_url(test_url)
        if result:
            print(f"Successfully scraped: {result}")
        else:
            print("No data found")


if __name__ == "__main__":
    asyncio.run(main())
