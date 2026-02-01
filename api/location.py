# api/location.py
"""
Location API endpoints for Opentrace
Provides location-aware search, geocoding, and spatial queries.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func
from sqlalchemy.orm import selectinload
from typing import Optional, List
from pydantic import BaseModel
import math

from db.session import get_db_session
from models.person import Person
from models.location import Location, PersonLocation
from services.location_resolver import location_resolver
from auth.deps import require_admin_role
from auth.models import AdminUser

router = APIRouter(prefix="/api", tags=["location"])


class LocationResolveRequest(BaseModel):
    text: str
    context: Optional[str] = None


class LocationResolveResponse(BaseModel):
    location_id: str
    display_name: str
    canonical_name: str
    latitude: float
    longitude: float
    coordinate_precision: str
    country_code: str
    country_name: str
    admin1_name: Optional[str]
    locality: Optional[str]
    location_type: str
    confidence_score: float


class NearbySearchRequest(BaseModel):
    latitude: float
    longitude: float
    radius_km: int = 50
    event_types: Optional[List[str]] = None


class PersonWithLocation(BaseModel):
    pfif_id: str
    given_name: Optional[str]
    family_name: Optional[str]
    age_at_disappearance: Optional[int]
    sex: Optional[str]
    status: str
    primary_source: Optional[str]
    locations: List[dict]


class LocationCreateRequest(BaseModel):
    location_id: str
    canonical_name: str
    display_name: str
    latitude: float
    longitude: float
    country_code: str
    country_name: str
    location_type: str
    admin1_name: Optional[str] = None
    locality: Optional[str] = None
    coordinate_precision: Optional[str] = "approximate"


class LocationUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    canonical_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    admin1_name: Optional[str] = None
    locality: Optional[str] = None
    location_type: Optional[str] = None
    coordinate_precision: Optional[str] = None
    is_active: Optional[bool] = None


@router.post("/resolve-location", response_model=LocationResolveResponse)
async def resolve_location(
    request: LocationResolveRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Resolve free text location to canonical Location entity.
    
    Example:
    POST /api/resolve-location
    {
        "text": "Last seen near Venice Beach, Los Angeles",
        "context": "missing_person_report"
    }
    """
    try:
        location = await location_resolver.resolve_location(request.text, request.context)
        
        if not location:
            raise HTTPException(status_code=404, detail="Location not found")
        
        return LocationResolveResponse(
            location_id=location.location_id,
            display_name=location.display_name,
            canonical_name=location.canonical_name,
            latitude=float(location.latitude),
            longitude=float(location.longitude),
            coordinate_precision=location.coordinate_precision,
            country_code=location.country_code,
            country_name=location.country_name,
            admin1_name=location.admin1_name,
            locality=location.locality,
            location_type=location.location_type,
            confidence_score=float(location.confidence_score)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Location resolution failed: {str(e)}")


@router.get("/nearby", response_model=List[PersonWithLocation])
async def find_nearby_persons(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    radius: int = Query(50, description="Search radius in kilometers"),
    event_types: Optional[str] = Query(None, description="Comma-separated event types: last_seen,found,sighting"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Find persons within radius of coordinates using spatial search.
    
    Example:
    GET /api/nearby?lat=34.0522&lng=-118.2437&radius=50&event_types=last_seen,found
    """
    try:
        # Parse event types
        event_type_list = []
        if event_types:
            event_type_list = [t.strip() for t in event_types.split(',')]
        
        # Use PostGIS spatial query
        spatial_query = text("""
            SELECT DISTINCT p.pfif_id, p.given_name, p.family_name, p.age_at_disappearance, 
                   p.sex, p.status, p.primary_source,
                   l.location_id, l.display_name, l.latitude, l.longitude,
                   pl.event_type, pl.event_date, pl.event_description,
                   ST_Distance(
                       ST_SetSRID(ST_MakePoint(l.longitude, l.latitude), 4326),
                       ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)
                   ) as distance_km
            FROM person p
            JOIN person_location pl ON p.pfif_id = pl.pfif_id
            JOIN location l ON pl.location_id = l.location_id
            WHERE p.is_confirmed = true 
              AND p.is_active = true
              AND pl.is_public = true
              AND ST_DWithin(
                  ST_SetSRID(ST_MakePoint(l.longitude, l.latitude), 4326),
                  ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
                  :radius * 1000  -- Convert km to meters
              )
        """)
        
        # Add event type filter if specified
        if event_type_list:
            spatial_query = text(str(spatial_query) + 
                " AND pl.event_type = ANY(:event_types)")
        
        spatial_query = spatial_query.order_by(text("distance_km"))
        
        params = {"lat": lat, "lng": lng, "radius": radius}
        if event_type_list:
            params["event_types"] = event_type_list
        
        result = await db.execute(spatial_query, params)
        rows = result.fetchall()
        
        # Group by person
        persons_dict = {}
        for row in rows:
            pfif_id = row.pfif_id
            if pfif_id not in persons_dict:
                persons_dict[pfif_id] = {
                    "pfif_id": pfif_id,
                    "given_name": row.given_name,
                    "family_name": row.family_name,
                    "age_at_disappearance": row.age_at_disappearance,
                    "sex": row.sex,
                    "status": row.status,
                    "primary_source": row.primary_source,
                    "locations": []
                }
            
            # Add location event
            location_data = {
                "location_id": row.location_id,
                "display_name": row.display_name,
                "latitude": float(row.latitude),
                "longitude": float(row.longitude),
                "event_type": row.event_type,
                "event_date": row.event_date.isoformat() if row.event_date else None,
                "event_description": row.event_description,
                "distance_km": round(float(row.distance_km), 2)
            }
            persons_dict[pfif_id]["locations"].append(location_data)
        
        return list(persons_dict.values())
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Spatial search failed: {str(e)}")


@router.get("/locations/search", response_model=List[LocationResolveResponse])
async def search_locations(
    q: str = Query(..., description="Location search query"),
    limit: int = Query(10, description="Maximum results"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Search for locations by name.
    
    Example:
    GET /api/locations/search?q=Los Angeles&limit=5
    """
    try:
        query = select(Location).where(
            Location.is_active == True
        ).where(
            (Location.display_name.ilike(f"%{q}%")) |
            (Location.canonical_name.ilike(f"%{q}%")) |
            (Location.locality.ilike(f"%{q}%")) |
            (Location.admin1_name.ilike(f"%{q}%"))
        ).order_by(
            Location.confidence_score.desc(),
            Location.importance.desc()
        ).limit(limit)
        
        result = await db.execute(query)
        locations = result.scalars().all()
        
        return [
            LocationResolveResponse(
                location_id=loc.location_id,
                display_name=loc.display_name,
                canonical_name=loc.canonical_name,
                latitude=float(loc.latitude),
                longitude=float(loc.longitude),
                coordinate_precision=loc.coordinate_precision,
                country_code=loc.country_code,
                country_name=loc.country_name,
                admin1_name=loc.admin1_name,
                locality=loc.locality,
                location_type=loc.location_type,
                confidence_score=float(loc.confidence_score)
            )
            for loc in locations
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Location search failed: {str(e)}")


@router.get("/locations", response_model=List[LocationResolveResponse])
async def list_locations(
    q: Optional[str] = Query(None, description="Optional search query"),
    limit: int = Query(25, description="Maximum results"),
    db: AsyncSession = Depends(get_db_session)
):
    """List active locations with optional search query."""
    if db is None:
        return []
    try:
        query = select(Location).where(Location.is_active == True)
        if q:
            query = query.where(
                (Location.display_name.ilike(f"%{q}%")) |
                (Location.canonical_name.ilike(f"%{q}%")) |
                (Location.locality.ilike(f"%{q}%")) |
                (Location.admin1_name.ilike(f"%{q}%"))
            )
        query = query.order_by(Location.confidence_score.desc()).limit(limit)
        result = await db.execute(query)
        locations = result.scalars().all()
        return [
            LocationResolveResponse(
                location_id=loc.location_id,
                display_name=loc.display_name,
                canonical_name=loc.canonical_name,
                latitude=float(loc.latitude),
                longitude=float(loc.longitude),
                coordinate_precision=loc.coordinate_precision,
                country_code=loc.country_code,
                country_name=loc.country_name,
                admin1_name=loc.admin1_name,
                locality=loc.locality,
                location_type=loc.location_type,
                confidence_score=float(loc.confidence_score)
            )
            for loc in locations
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list locations: {str(e)}")


@router.get("/locations/{location_id}", response_model=LocationResolveResponse)
async def get_location(
    location_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Get a single location by ID."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    result = await db.execute(select(Location).where(Location.location_id == location_id))
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return LocationResolveResponse(
        location_id=location.location_id,
        display_name=location.display_name,
        canonical_name=location.canonical_name,
        latitude=float(location.latitude),
        longitude=float(location.longitude),
        coordinate_precision=location.coordinate_precision,
        country_code=location.country_code,
        country_name=location.country_name,
        admin1_name=location.admin1_name,
        locality=location.locality,
        location_type=location.location_type,
        confidence_score=float(location.confidence_score)
    )


@router.get("/persons/{pfif_id}/locations")
async def get_person_locations(
    pfif_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get all location events for a specific person.
    
    Example:
    GET /api/persons/opentrace.org/person/namus.MP24398/locations
    """
    try:
        # Get person
        person_result = await db.execute(
            select(Person).where(Person.pfif_id == pfif_id)
        )
        person = person_result.scalar_one_or_none()
        
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")
        
        # Get person locations with location details
        query = select(PersonLocation, Location).join(Location).where(
            PersonLocation.pfif_id == pfif_id,
            PersonLocation.is_public == True
        ).order_by(PersonLocation.event_date.desc().nullslast())
        
        result = await db.execute(query)
        rows = result.fetchall()
        
        locations = []
        for person_loc, location in rows:
            locations.append(person_loc.to_dict(location))
        
        return {
            "person": person.to_public_dict(),
            "locations": locations
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get person locations: {str(e)}")


@router.post("/persons/{pfif_id}/locations")
async def add_person_location(
    pfif_id: str,
    location_data: dict,
    db: AsyncSession = Depends(get_db_session),
    admin: AdminUser = Depends(require_admin_role("admin"))
):
    """
    Add a location event for a person.
    
    Example:
    POST /api/persons/opentrace.org/person/namus.MP24398/locations
    {
        "text": "Venice Beach, Los Angeles",
        "event_type": "sighting",
        "event_date": "2024-01-15T10:00:00Z",
        "event_description": "Seen near the pier",
        "source_url": "https://example.com/report"
    }
    """
    try:
        # Verify person exists
        person_result = await db.execute(
            select(Person).where(Person.pfif_id == pfif_id)
        )
        person = person_result.scalar_one_or_none()
        
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")
        
        # Resolve location
        location = await location_resolver.resolve_location(
            location_data.get('text', ''),
            location_data.get('context', 'user_report')
        )
        
        if not location:
            raise HTTPException(status_code=400, detail="Could not resolve location")
        
        # Create person-location relationship
        person_location = await location_resolver.create_person_location(
            pfif_id=pfif_id,
            location=location,
            event_type=location_data.get('event_type', 'sighting'),
            event_date=location_data.get('event_date'),
            description=location_data.get('event_description'),
            source_url=location_data.get('source_url')
        )
        
        return {
            "message": "Location added successfully",
            "person_location": person_location.to_dict(location)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add location: {str(e)}")


@router.post("/locations", status_code=status.HTTP_201_CREATED)
async def create_location(
    request: LocationCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    admin: AdminUser = Depends(require_admin_role("admin"))
):
    """Create a new location (admin-only)."""
    location = Location(
        location_id=request.location_id,
        canonical_name=request.canonical_name,
        display_name=request.display_name,
        latitude=request.latitude,
        longitude=request.longitude,
        country_code=request.country_code,
        country_name=request.country_name,
        admin1_name=request.admin1_name,
        locality=request.locality,
        location_type=request.location_type,
        coordinate_precision=request.coordinate_precision
    )
    db.add(location)
    await db.commit()
    return {"location_id": request.location_id}


@router.patch("/locations/{location_id}")
async def update_location(
    location_id: str,
    request: LocationUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    admin: AdminUser = Depends(require_admin_role("admin"))
):
    """Update an existing location (admin-only)."""
    result = await db.execute(select(Location).where(Location.location_id == location_id))
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    for key, value in request.model_dump(exclude_unset=True).items():
        setattr(location, key, value)
    await db.commit()
    return {"message": "Location updated"}


@router.delete("/locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    location_id: str,
    db: AsyncSession = Depends(get_db_session),
    admin: AdminUser = Depends(require_admin_role("admin"))
):
    """Soft delete a location (admin-only)."""
    result = await db.execute(select(Location).where(Location.location_id == location_id))
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    location.is_active = False
    await db.commit()
    return None


@router.get("/reverse-geocode", response_model=LocationResolveResponse)
async def reverse_geocode(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Reverse geocode coordinates to location.
    
    Example:
    GET /api/reverse-geocode?lat=34.0522&lng=-118.2437
    """
    try:
        location = await location_resolver.resolve_coordinates(lat, lng)
        
        if not location:
            raise HTTPException(status_code=404, detail="Location not found for coordinates")
        
        return LocationResolveResponse(
            location_id=location.location_id,
            display_name=location.display_name,
            canonical_name=location.canonical_name,
            latitude=float(location.latitude),
            longitude=float(location.longitude),
            coordinate_precision=location.coordinate_precision,
            country_code=location.country_code,
            country_name=location.country_name,
            admin1_name=location.admin1_name,
            locality=location.locality,
            location_type=location.location_type,
            confidence_score=float(location.confidence_score)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reverse geocoding failed: {str(e)}")
