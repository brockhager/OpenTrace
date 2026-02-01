import asyncio
import hashlib
import re
from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional, Dict, Any
from urllib.parse import urlparse

import httpx
from pdfminer.high_level import extract_text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import async_session
from api.models import IntelItem, AuditLog


class PDFProcessor:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def validate_url(self, url: str) -> bool:
        """Validate URL is public HTTPS."""
        parsed = urlparse(url)
        return (
            parsed.scheme == "https" and
            parsed.netloc and
            not parsed.netloc.startswith("localhost") and
            not parsed.netloc.startswith("127.") and
            not parsed.netloc.startswith("192.168.") and
            not parsed.netloc.startswith("10.") and
            not parsed.netloc.startswith("172.")
        )

    async def fetch_pdf(self, url: str) -> Optional[bytes]:
        """Fetch PDF content in memory."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            if "application/pdf" not in response.headers.get("content-type", "").lower():
                return None
            return response.content
        except Exception:
            return None

    def extract_text(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF using pdfminer."""
        try:
            with BytesIO(pdf_bytes) as bio:
                text = extract_text(bio)
            return text
        except Exception:
            return ""

    def redact_pii(self, text: str) -> str:
        """Aggressively redact PII."""
        # Phone numbers: various formats
        text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE REDACTED]', text)
        text = re.sub(r'\b\d{10}\b', '[PHONE REDACTED]', text)
        # Emails
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL REDACTED]', text)
        # Addresses: simple heuristic, remove lines with street keywords
        lines = text.split('\n')
        redacted_lines = []
        for line in lines:
            if re.search(r'\b(street|avenue|road|drive|lane|blvd|place|court)\b', line.lower()):
                redacted_lines.append('[ADDRESS REDACTED]')
            else:
                redacted_lines.append(line)
        return '\n'.join(redacted_lines)

    def extract_entities(self, text: str) -> Dict[str, Any]:
        """Extract possible names, locations, dates."""
        names = []
        locations = []
        dates = []

        # Names: Capitalized words, 2-3 words
        name_pattern = re.compile(r'\b[A-Z][a-z]+(?: [A-Z][a-z]+){1,2}\b')
        names = name_pattern.findall(text)

        # Locations: US states, major cities (simple list)
        states = ['Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado', 'Connecticut', 'Delaware', 'Florida', 'Georgia', 'Hawaii', 'Idaho', 'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky', 'Louisiana', 'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota', 'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada', 'New Hampshire', 'New Jersey', 'New Mexico', 'New York', 'North Carolina', 'North Dakota', 'Ohio', 'Oklahoma', 'Oregon', 'Pennsylvania', 'Rhode Island', 'South Carolina', 'South Dakota', 'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia', 'Washington', 'West Virginia', 'Wisconsin', 'Wyoming']
        cities = ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix', 'Philadelphia', 'San Antonio', 'San Diego', 'Dallas', 'San Jose', 'Austin', 'Jacksonville', 'Fort Worth', 'Columbus', 'Charlotte', 'San Francisco', 'Indianapolis', 'Seattle', 'Denver', 'Boston', 'El Paso', 'Detroit', 'Nashville', 'Portland', 'Memphis', 'Oklahoma City', 'Las Vegas', 'Louisville', 'Baltimore', 'Milwaukee', 'Albuquerque', 'Tucson', 'Fresno', 'Sacramento', 'Mesa', 'Kansas City', 'Atlanta', 'Long Beach', 'Colorado Springs', 'Raleigh', 'Miami', 'Virginia Beach', 'Omaha', 'Oakland', 'Minneapolis', 'Tulsa', 'Arlington', 'Tampa', 'New Orleans', 'Wichita', 'Cleveland', 'Bakersfield', 'Aurora', 'Anaheim', 'Honolulu', 'Santa Ana', 'Corpus Christi', 'Riverside', 'Lexington', 'Stockton', 'Henderson', 'Saint Paul', 'St. Louis', 'Cincinnati', 'Pittsburgh', 'Greensboro', 'Anchorage', 'Plano', 'Lincoln', 'Orlando', 'Irvine', 'Newark', 'Durham', 'Chula Vista', 'Toledo', 'Fort Wayne', 'St. Petersburg', 'Laredo', 'Jersey City', 'Chandler', 'Madison', 'Lubbock', 'Scottsdale', 'Reno', 'Buffalo', 'Gilbert', 'Glendale', 'North Las Vegas', 'Winston-Salem', 'Chesapeake', 'Norfolk', 'Fremont', 'Garland', 'Irving', 'Hialeah', 'Richmond', 'Boise', 'Spokane', 'Baton Rouge']
        for word in re.findall(r'\b[A-Z][a-z]+\b', text):
            if word in states or word in cities:
                locations.append(word)

        # Dates: YYYY-MM-DD or "Month Year"
        date_pattern = re.compile(r'\b\d{4}-\d{2}-\d{2}\b')
        dates = date_pattern.findall(text)
        month_year = re.findall(r'\b(January|February|March|April|May|June|July|August|September|October|November|December) \d{4}\b', text)
        dates.extend(month_year)

        return {
            "possible_names": list(set(names))[:5],  # Limit
            "possible_locations": list(set(locations))[:5],
            "possible_dates": list(set(dates))[:5]
        }

    async def process_pdf(self, pdf_url: str, note: str, db: AsyncSession):
        """Process PDF and create intel_item."""
        if not self.validate_url(pdf_url):
            return  # Invalid URL

        pdf_bytes = await self.fetch_pdf(pdf_url)
        if not pdf_bytes:
            return  # Not a PDF or fetch failed

        text = self.extract_text(pdf_bytes)
        if not text.strip():
            return  # No text

        redacted_text = self.redact_pii(text)
        entities = self.extract_entities(redacted_text)

        # Create summary
        summary = f"PDF Document: {note}\nPossible Names: {', '.join(entities['possible_names'])}\nLocations: {', '.join(entities['possible_locations'])}\nDates: {', '.join(entities['possible_dates'])}"

        # Anonymous hash
        anonymous_hash = hashlib.sha256(pdf_url.encode()).hexdigest()[:16]

        # Create intel_item
        intel = IntelItem(
            person_pfif_id=None,  # No specific person
            author_name="Community PDF Submission",
            source_url=pdf_url,
            text=summary,
            category="pdf_document",
            confidence_rating="low",  # Unverified
            reviewed=False
        )
        db.add(intel)
        await db.flush()  # Get ID

        # Audit log
        audit = AuditLog(
            action="ingest_pdf",
            actor_id=anonymous_hash,
            target_id=str(intel.id),
            details={"pdf_url": pdf_url, "note": note}
        )
        db.add(audit)

        await db.commit()