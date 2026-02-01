# services/location_resolver.py
"""
Location Resolution Service - Geocoding and canonicalization for Opentrace
Converts free text location descriptions to standardized geographic entities.
"""

import asyncio
import re
import aiohttp
from typing import Optional, Dict, List, Tuple, Any
from urllib.parse import quote
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from models.location import Location, PersonLocation
from db.session import async_session

logger = logging.getLogger(__name__)


class LocationResolver:
    """
    Service for resolving free text location descriptions to canonical Location entities.
    
    Uses multiple geocoding services with fallback strategies and confidence scoring.
    """
    
    def __init__(self):
        self.session_timeout = 30
        self.user_agent = "Opentrace/1.0 (Geocoding Service)"
        
        # Geocoding service endpoints (free tiers)
        self.geonames_url = "http://api.geonames.org/searchJSON"
        self.nominatim_url = "https://nominatim.openstreetmap.org/search"
        
        # API keys (set in environment)
        self.geonames_username = "opentrace"  # Replace with actual username
        
    async def resolve_location(self, text: str, context: str = None) -> Optional[Location]:
        """
        Resolve free text location to canonical Location entity.
        
        Args:
            text: Free text location description
            context: Optional context (e.g., "missing_person_report")
            
        Returns:
            Location entity or None if resolution failed
        """
        if not text or len(text.strip()) < 2:
            return None
            
        # Clean and normalize input
        clean_text = self._clean_location_text(text)
        
        # Try exact match first
        existing_location = await self._find_existing_location(clean_text)
        if existing_location:
            return existing_location
            
        # Try geocoding services
        location_data = await self._geocode_text(clean_text)
        if not location_data:
            logger.warning(f"Failed to geocode location: {text}")
            return None
            
        # Create canonical Location entity
        location = await self._create_location_from_geodata(location_data, clean_text, context)
        
        return location
    
    def _clean_location_text(self, text: str) -> str:
        """Clean and normalize location text."""
        # Remove common prefixes/suffixes
        text = re.sub(r'(?i)^(last seen near|found near|reported from|near|around)\s+', '', text.strip())
        text = re.sub(r'(?i)\s+(area|region|county|city|town)$', '', text.strip())
        
        # Standardize separators
        text = re.sub(r'\s*,\s*', ', ', text)
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    async def _find_existing_location(self, text: str) -> Optional[Location]:
        """Find existing location by exact or fuzzy match."""
        async with async_session() as db:
            # Try exact display name match
            result = await db.execute(
                select(Location).where(
                    (Location.display_name.ilike(f"%{text}%")) |
                    (Location.canonical_name.ilike(f"%{text}%")) |
                    (Location.locality.ilike(f"%{text}%"))
                ).limit(5)
            )
            
            locations = result.scalars().all()
            if locations:
                # Return highest confidence match
                return max(locations, key=lambda loc: loc.confidence_score)
                
        return None
    
    async def _geocode_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Try multiple geocoding services in order."""
        
        # Try OpenStreetMap Nominatim first (free, no API key required)
        geodata = await self._geocode_nominatim(text)
        if geodata:
            return geodata
            
        # Fallback to GeoNames (requires username)
        geodata = await self._geocode_geonames(text)
        if geodata:
            return geodata
            
        return None
    
    async def _geocode_nominatim(self, text: str) -> Optional[Dict[str, Any]]:
        """Geocode using OpenStreetMap Nominatim API."""
        try:
            params = {
                'q': text,
                'format': 'json',
                'limit': 5,
                'addressdetails': 1,
                'countrycodes': 'us,ca,mx,gb,fr,de,au'  # Prioritize English-speaking countries
            }
            
            url = f"{self.nominatim_url}?{quote(text)}"
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.session_timeout),
                headers={'User-Agent': self.user_agent}
            ) as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data:
                            return self._parse_nominatim_response(data[0])
                            
        except Exception as e:
            logger.error(f"Nominatim geocoding failed: {e}")
            
        return None
    
    async def _geocode_geonames(self, text: str) -> Optional[Dict[str, Any]]:
        """Geocode using GeoNames API."""
        try:
            params = {
                'q': text,
                'maxRows': 5,
                'username': self.geonames_username,
                'style': 'FULL',
                'featureClass': 'P',  # Populated places
                'lang': 'en'
            }
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.session_timeout)
            ) as session:
                async with session.get(self.geonames_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('geonames'):
                            return self._parse_geonames_response(data['geonames'][0])
                            
        except Exception as e:
            logger.error(f"GeoNames geocoding failed: {e}")
            
        return None
    
    def _parse_nominatim_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Nominatim API response into standard format."""
        address = data.get('address', {})
        
        return {
            'display_name': data.get('display_name', ''),
            'latitude': float(data.get('lat', 0)),
            'longitude': float(data.get('lon', 0)),
            'country_code': address.get('country_code', '').upper(),
            'country_name': address.get('country', ''),
            'admin1_name': address.get('state', '') or address.get('province', ''),
            'admin2_name': address.get('county', ''),
            'locality': address.get('city', '') or address.get('town', '') or address.get('village', ''),
            'location_type': self._classify_location_type(data.get('type', ''), data.get('class', '')),
            'importance': float(data.get('importance', 0.5)),
            'confidence_score': 0.85,  # Nominatim is generally reliable
            'source_system': 'nominatim',
            'source_data': data
        }
    
    def _parse_geonames_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse GeoNames API response into standard format."""
        return {
            'display_name': data.get('name', ''),
            'latitude': float(data.get('lat', 0)),
            'longitude': float(data.get('lng', 0)),
            'country_code': data.get('countryCode', '').upper(),
            'country_name': data.get('countryName', ''),
            'admin1_code': data.get('adminCode1', ''),
            'admin1_name': data.get('adminName1', ''),
            'admin2_code': data.get('adminCode2', ''),
            'admin2_name': data.get('adminName2', ''),
            'locality': data.get('name', ''),
            'location_type': self._map_geonames_type(data.get('fcl', ''), data.get('fcode', '')),
            'population': int(data.get('population', 0)) if data.get('population') else None,
            'importance': self._calculate_importance_from_population(data.get('population', 0)),
            'confidence_score': 0.75,  # GeoNames is good but sometimes outdated
            'source_system': 'geonames',
            'source_data': data
        }
    
    def _classify_location_type(self, osm_type: str, osm_class: str) -> str:
        """Classify location type from OpenStreetMap data."""
        if osm_class == 'place':
            type_mapping = {
                'city': 'city',
                'town': 'city', 
                'village': 'city',
                'hamlet': 'city',
                'county': 'county',
                'state': 'state',
                'country': 'country'
            }
            return type_mapping.get(osm_type, 'landmark')
        elif osm_class == 'boundary':
            return 'administrative'
        else:
            return 'landmark'
    
    def _map_geonames_type(self, fcl: str, fcode: str) -> str:
        """Map GeoNames feature class/code to location type."""
        if fcl == 'P':  # Populated place
            if fcode.startswith('PPL'):
                return 'city'
            elif fcode == 'PPLA':  # Seat of first-order administrative division
                return 'city'
            elif fcode == 'PPLC':  # Capital
                return 'city'
        elif fcl == 'A':  # Administrative boundary
            return 'administrative'
        elif fcl == 'L':  # Parks, area, etc.
            return 'landmark'
        
        return 'landmark'
    
    def _calculate_importance_from_population(self, population: int) -> float:
        """Calculate importance score based on population."""
        if not population or population <= 0:
            return 0.1
            
        # Logarithmic scale: 1M+ = 1.0, 100K = 0.8, 10K = 0.6, 1K = 0.4, <1K = 0.2
        if population >= 1000000:
            return 1.0
        elif population >= 100000:
            return 0.8
        elif population >= 10000:
            return 0.6
        elif population >= 1000:
            return 0.4
        else:
            return 0.2
    
    async def _create_location_from_geodata(self, geodata: Dict[str, Any], original_text: str, context: str) -> Location:
        """Create Location entity from geocoding data."""
        
        # Generate canonical location ID
        location_id = self._generate_location_id(geodata)
        
        # Create canonical name
        canonical_parts = []
        if geodata.get('locality'):
            canonical_parts.append(geodata['locality'])
        if geodata.get('admin2_name') and geodata['admin2_name'] != geodata.get('locality'):
            canonical_parts.append(geodata['admin2_name'])
        if geodata.get('admin1_name'):
            canonical_parts.append(geodata['admin1_name'])
        if geodata.get('country_name'):
            canonical_parts.append(geodata['country_name'])
        
        canonical_name = ", ".join(canonical_parts)
        display_name = geodata.get('display_name', original_text)
        
        # Create Location entity
        location = Location(
            location_id=location_id,
            canonical_name=canonical_name,
            display_name=display_name,
            latitude=geodata['latitude'],
            longitude=geodata['longitude'],
            coordinate_precision='approximate',  # Most geocoding is approximate
            country_code=geodata.get('country_code', ''),
            country_name=geodata.get('country_name', ''),
            admin1_name=geodata.get('admin1_name'),
            admin2_name=geodata.get('admin2_name'),
            locality=geodata.get('locality'),
            location_type=geodata.get('location_type', 'landmark'),
            population=geodata.get('population'),
            importance=geodata.get('importance', 0.5),
            confidence_score=geodata.get('confidence_score', 0.5),
            source_system=geodata.get('source_system', 'unknown'),
            source_data=geodata.get('source_data')
        )
        
        # Save to database
        async with async_session() as db:
            db.add(location)
            await db.commit()
            await db.refresh(location)
        
        logger.info(f"Created location: {location_id} - {display_name}")
        return location
    
    def _generate_location_id(self, geodata: Dict[str, Any]) -> str:
        """Generate canonical location ID from geodata."""
        parts = []
        
        # Add locality (lowercase, spaces to hyphens)
        if geodata.get('locality'):
            locality = re.sub(r'\s+', '-', geodata['locality'].lower())
            parts.append(locality)
        
        # Add admin1 code if available
        if geodata.get('admin1_code'):
            parts.append(geodata['admin1_code'].lower())
        elif geodata.get('admin1_name'):
            admin1 = re.sub(r'\s+', '-', geodata['admin1_name'].lower())
            parts.append(admin1)
        
        # Add country code
        if geodata.get('country_code'):
            parts.append(geodata['country_code'].lower())
        
        return "-".join(parts) if parts else f"location-{hash(str(geodata)) % 10000}"
    
    async def resolve_coordinates(self, lat: float, lng: float) -> Optional[Location]:
        """Reverse geocode coordinates to Location entity."""
        try:
            params = {
                'lat': lat,
                'lon': lng,
                'format': 'json',
                'addressdetails': 1,
                'zoom': 10  # City level
            }
            
            url = f"https://nominatim.openstreetmap.org/reverse"
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.session_timeout),
                headers={'User-Agent': self.user_agent}
            ) as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data:
                            geodata = self._parse_nominatim_response(data)
                            return await self._create_location_from_geodata(
                                geodata, f"Coordinates {lat},{lng}", "reverse_geocode"
                            )
                            
        except Exception as e:
            logger.error(f"Reverse geocoding failed for {lat},{lng}: {e}")
            
        return None
    
    async def create_person_location(
        self, 
        pfif_id: str, 
        location: Location, 
        event_type: str,
        event_date=None,
        description=None,
        source_url=None
    ) -> PersonLocation:
        """Create Person-Location relationship."""
        
        person_location = PersonLocation(
            pfif_id=pfif_id,
            location_id=location.location_id,
            event_type=event_type,
            event_date=event_date,
            event_description=description,
            source_url=source_url,
            source_confidence='medium',
            is_verified=False,
            is_public=True,
            created_by='location_resolver'
        )
        
        async with async_session() as db:
            db.add(person_location)
            await db.commit()
            await db.refresh(person_location)
        
        logger.info(f"Created person-location: {pfif_id} -> {location.location_id} ({event_type})")
        return person_location


# Singleton instance
location_resolver = LocationResolver()
