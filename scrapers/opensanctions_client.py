import asyncio
import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import uuid4

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import async_session
from api.models import PersonProfile, AuditLog


class OpenSanctionsClient:
    BASE_URL = "https://api.opensanctions.org/search"
    RATE_LIMIT_DELAY = 6  # 10 requests/minute = 6s delay

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def fetch_batch(self, cursor: Optional[str] = None) -> Dict[str, Any]:
        params = {
            "dataset": "interpol_yellow_notices",
            "schema": "Person",
            "limit": 100
        }
        if cursor:
            params["cursor"] = cursor

        response = await self.client.get(self.BASE_URL, params=params)
        response.raise_for_status()
        return response.json()

    def map_to_profile(self, record: Dict[str, Any]) -> Optional[PersonProfile]:
        """Map OpenSanctions record to PersonProfile. Skip if missing name or birthDate."""
        properties = record.get("properties", {})

        name = properties.get("name")
        if not name:
            return None

        birth_date_str = properties.get("birthDate", [None])[0]
        if not birth_date_str:
            return None

        # Calculate age
        try:
            birth_date = datetime.fromisoformat(birth_date_str.replace('Z', '+00:00'))
            age = (datetime.utcnow() - birth_date).days // 365
        except (ValueError, TypeError):
            age = None

        # Split name into given/family (simple split on space)
        name_parts = name.split(" ", 1)
        given_name = name_parts[0] if len(name_parts) > 1 else None
        family_name = name_parts[1] if len(name_parts) > 1 else name_parts[0]

        # Last seen location
        addresses = properties.get("address", [])
        last_seen_location = addresses[0].get("full") if addresses else None

        # Gender
        gender_map = {"male": "Male", "female": "Female"}
        sex = gender_map.get(properties.get("gender", [None])[0])

        pfif_id = f"opentrace.org/person.interpol.{record['id']}"

        return PersonProfile(
            pfif_id=pfif_id,
            author_name="OpenSanctions",
            given_name=given_name,
            family_name=family_name,
            age=age,
            sex=sex,
            last_seen_location=last_seen_location,
            status="missing",
            is_confirmed=False,  # Requires admin review
            source_date=birth_date_str,
            profile_url=properties.get("sourceUrl", [None])[0]
        )

    async def ingest_batch(self, db: AsyncSession, records: list) -> int:
        """Ingest a batch of records into DB. Return count of new profiles."""
        new_count = 0
        for record in records:
            profile = self.map_to_profile(record)
            if not profile:
                continue

            # Check if exists
            existing = await db.execute(select(PersonProfile).where(PersonProfile.pfif_id == profile.pfif_id))
            if existing.scalar_one_or_none():
                continue

            db.add(profile)
            new_count += 1

        await db.commit()
        return new_count

    async def ingest_all(self, db: AsyncSession, max_batches: Optional[int] = None) -> Dict[str, Any]:
        """Ingest all available records. Return stats."""
        total_ingested = 0
        batches = 0
        cursor = None

        while max_batches is None or batches < max_batches:
            try:
                data = await self.fetch_batch(cursor)
                records = data.get("results", [])
                if not records:
                    break

                batch_count = await self.ingest_batch(db, records)
                total_ingested += batch_count
                batches += 1

                cursor = data.get("next")
                if not cursor:
                    break

                # Rate limit
                await asyncio.sleep(self.RATE_LIMIT_DELAY)

            except Exception as e:
                # Log error and continue or break
                print(f"Error in batch {batches}: {e}")
                break

        # Audit log
        audit = AuditLog(
            action="ingest_opensanctions",
            actor_id="system",
            details={"total_ingested": total_ingested, "batches": batches}
        )
        db.add(audit)
        await db.commit()

        return {"total_ingested": total_ingested, "batches": batches}