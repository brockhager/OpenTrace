#!/usr/bin/env python3
"""
Bulk ingestion script for global OSINT sources.
Usage:
  python scripts/ingest_global.py --source opensanctions --batch-size 50
  python scripts/ingest_global.py --source charley --max-pages 100
"""
import asyncio
import argparse
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import async_session
from scrapers.opensanctions_client import OpenSanctionsClient
from scrapers.charley_scraper import CharleyScraper


async def ingest_opensanctions(batch_size: int):
    async with async_session() as db:
        async with OpenSanctionsClient() as client:
            stats = await client.ingest_all(db, max_batches=batch_size)
            print(f"OpenSanctions ingestion complete: {stats}")


async def ingest_charley(max_pages: int):
    async with async_session() as db:
        async with CharleyScraper() as scraper:
            stats = await scraper.ingest_pages(db, max_pages=max_pages)
            print(f"Charley Project ingestion complete: {stats}")


async def main():
    parser = argparse.ArgumentParser(description="Ingest global OSINT data into Opentrace.")
    parser.add_argument("--source", required=True, choices=["opensanctions", "charley"], help="Data source to ingest")
    parser.add_argument("--batch-size", type=int, default=10, help="Max batches for OpenSanctions (default: 10)")
    parser.add_argument("--max-pages", type=int, default=10, help="Max pages for Charley Project (default: 10)")

    args = parser.parse_args()

    if args.source == "opensanctions":
        await ingest_opensanctions(args.batch_size)
    elif args.source == "charley":
        await ingest_charley(args.max_pages)


if __name__ == "__main__":
    asyncio.run(main())