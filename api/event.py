# api/event.py
"""
Event API endpoints for Opentrace
Provides CRUD operations for the Event entity with immutability enforcement.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, or_, func
from sqlalchemy.orm import selectinload
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID

from db.session import get_db_session
from auth.deps import require_admin_role
from auth.models import AdminUser
from models.event import Event
from models.person import Person
from models.location import Location
from core.logger import logger

router = APIRouter(prefix="/api/events", tags=["events"])

VALID_EVENT_TYPES = {
    "sighting", "police_report", "status_change", "tip", "document",
    "recovery", "false_alarm", "digital_trace",
    "movement", "inspection", "handover", "report",
    "departure", "arrival", "contact", "other"
}


# Pydantic request/response models
class EventCreateRequest(BaseModel):
    """Request model for creating a new event."""
    name: Optional[str] = Field(None, max_length=255, description="Human-readable label")
    event_type: str = Field(..., description="Type of event: movement, inspection, handover, sighting, report, other")
    event_timestamp: datetime = Field(..., description="ISO 8601 datetime of when the event occurred")
    profile: Optional[dict] = Field(None, description="Structured metadata as JSON object")
    person_id: Optional[str] = Field(None, description="Reference to person.pfif_id")
    location_id: Optional[str] = Field(None, description="Reference to location.location_id")
    source_type: Optional[str] = Field("user_report", description="Source: user_report, system_generated, api, import")
    source_url: Optional[str] = Field(None, description="URL or reference to source documentation")
    confidence_score: Optional[str] = Field("medium", description="high, medium, low")
    is_public: Optional[str] = Field("public", description="public, restricted, private")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Departure",
                "event_type": "movement",
                "event_timestamp": "2024-01-15T10:30:00Z",
                "profile": {
                    "transport_mode": "vehicle",
                    "destination": "Los Angeles",
                    "notes": "Left for work"
                },
                "person_id": "opentrace.org/person/namus.MP24398",
                "location_id": "los-angeles-ca-usa",
                "source_type": "user_report",
                "confidence_score": "medium"
            }
        }


class EventResponse(BaseModel):
    """Response model for event data."""
    event_id: str
    name: Optional[str]
    event_type: str
    event_timestamp: str
    profile: Optional[dict]
    person_id: Optional[str]
    location_id: Optional[str]
    confidence_score: str
    is_verified: str
    is_public: str
    created_at: str
    source_type: Optional[str]
    source_url: Optional[str]
    
    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    """Response model for list of events."""
    events: List[EventResponse]
    total: int
    page: int
    page_size: int


class EventSearchParams(BaseModel):
    """Query parameters for event search."""
    person_id: Optional[str] = None
    location_id: Optional[str] = None
    event_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_verified: Optional[str] = None
    is_public: Optional[str] = None
    confidence_score: Optional[str] = None


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    request: EventCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    admin: AdminUser = Depends(require_admin_role("admin"))
):
    """
    Create a new event.
    
    Events are immutable once created - no updates allowed.
    This ensures audit integrity for the traceability graph.
    
    Example:
    POST /api/events
    {
        "name": "Departure",
        "event_type": "movement",
        "event_timestamp": "2024-01-15T10:30:00Z",
        "profile": {"transport_mode": "vehicle"},
        "person_id": "opentrace.org/person/namus.MP24398",
        "location_id": "los-angeles-ca-usa"
    }
    """
    try:
        if request.event_type not in VALID_EVENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid event_type. Must be one of: {', '.join(sorted(VALID_EVENT_TYPES))}"
            )
        if db is None:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not configured")
        # Validate person_id if provided
        if request.person_id:
            person_result = await db.execute(
                select(Person).where(Person.pfif_id == request.person_id)
            )
            if not person_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Person with pfif_id '{request.person_id}' not found"
                )
        
        # Validate location_id if provided
        if request.location_id:
            location_result = await db.execute(
                select(Location).where(Location.location_id == request.location_id)
            )
            if not location_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Location with location_id '{request.location_id}' not found"
                )
        
        # Create event (map person_id to pfif_id for model compatibility)
        event = Event(
            name=request.name,
            event_type=request.event_type,
            event_date=request.event_timestamp,  # Store in event_date field
            event_timestamp=request.event_timestamp,
            reported_date=datetime.now(),
            pfif_id=request.person_id,  # Map person_id to pfif_id
            location_id=request.location_id,
            profile=request.profile,
            source_type=request.source_type,
            source_url=request.source_url,
            source_confidence=request.confidence_score,
            is_public=request.is_public == "public",  # Convert string to boolean
            created_by=admin.email
        )
        
        db.add(event)
        await db.commit()
        await db.refresh(event)
        
        logger.info(
            "Event created",
            extra={
                "event_id": str(event.event_id),
                "event_type": event.event_type,
                "person_id": event.person_id,
                "location_id": event.location_id,
                "action": "event_create"
            }
        )
        
        return EventResponse(
            event_id=str(event.event_id),
            name=event.name,
            event_type=event.event_type,
            event_timestamp=event.event_timestamp.isoformat() if event.event_timestamp else None,
            profile=event.profile,
            person_id=event.pfif_id,
            location_id=event.location_id,
            confidence_score=event.source_confidence,
            is_verified=event.is_verified,
            is_public=event.is_public,
            created_at=event.created_at.isoformat() if event.created_at else None,
            source_type=event.source_type,
            source_url=event.source_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to create event",
            extra={"error": str(e), "action": "event_create_error"}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create event: {str(e)}"
        )


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get a specific event by ID.
    
    Example:
    GET /api/events/550e8400-e29b-41d4-a716-446655440000
    """
    try:
        if db is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database not configured")
        result = await db.execute(
            select(Event).where(Event.event_id == event_id)
        )
        event = result.scalar_one_or_none()
        
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event with id '{event_id}' not found"
            )
        
        return EventResponse(
            event_id=str(event.event_id),
            name=event.name,
            event_type=event.event_type,
            event_timestamp=event.event_timestamp.isoformat() if event.event_timestamp else None,
            profile=event.profile,
            person_id=event.pfif_id,
            location_id=event.location_id,
            confidence_score=event.source_confidence,
            is_verified=event.is_verified,
            is_public=event.is_public,
            created_at=event.created_at.isoformat() if event.created_at else None,
            source_type=event.source_type,
            source_url=event.source_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get event",
            extra={"error": str(e), "event_id": event_id, "action": "event_get_error"}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve event: {str(e)}"
        )


@router.get("", response_model=EventListResponse)
async def list_events(
    person_id: Optional[str] = Query(None, description="Filter by person"),
    location_id: Optional[str] = Query(None, description="Filter by location"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    start_date: Optional[datetime] = Query(None, description="Filter events after this date"),
    end_date: Optional[datetime] = Query(None, description="Filter events before this date"),
    is_verified: Optional[str] = Query(None, description="Filter by verification status"),
    is_public: Optional[str] = Query(None, description="Filter by visibility"),
    confidence_score: Optional[str] = Query(None, description="Filter by confidence"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    List events with optional filtering.
    
    Example:
    GET /api/events?person_id=opentrace.org/person/namus.MP24398&event_type=movement
    GET /api/events?location_id=los-angeles-ca-usa&start_date=2024-01-01
    """
    try:
        if db is None:
            return EventListResponse(events=[], total=0, page=page, page_size=page_size)
        # Build query
        query = select(Event)
        
        # Apply filters
        if person_id:
            query = query.where(Event.pfif_id == person_id)
        if location_id:
            query = query.where(Event.location_id == location_id)
        if event_type:
            query = query.where(Event.event_type == event_type)
        if start_date:
            query = query.where(Event.event_timestamp >= start_date)
        if end_date:
            query = query.where(Event.event_timestamp <= end_date)
        if is_verified:
            verified_bool = str(is_verified).lower() in ["true", "1", "verified", "yes"]
            query = query.where(Event.is_verified == verified_bool)
        if is_public:
            public_bool = str(is_public).lower() in ["true", "1", "public", "yes"]
            query = query.where(Event.is_public == public_bool)
        if confidence_score:
            query = query.where(Event.source_confidence == confidence_score)
        
        # Order by timestamp descending (newest first)
        query = query.order_by(desc(Event.event_timestamp))
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        # Execute query
        result = await db.execute(query)
        events = result.scalars().all()
        
        return EventListResponse(
            events=[
                EventResponse(
                    event_id=str(event.event_id),
                    name=event.name,
                    event_type=event.event_type,
                    event_timestamp=event.event_timestamp.isoformat() if event.event_timestamp else None,
                    profile=event.profile,
                    person_id=event.pfif_id,
                    location_id=event.location_id,
                    confidence_score=event.source_confidence,
                    is_verified=event.is_verified,
                    is_public=event.is_public,
                    created_at=event.created_at.isoformat() if event.created_at else None,
                    source_type=event.source_type,
                    source_url=event.source_url
                )
                for event in events
            ],
            total=total,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(
            "Failed to list events",
            extra={"error": str(e), "action": "event_list_error"}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list events: {str(e)}"
        )


@router.get("/person/{person_id}/timeline")
async def get_person_timeline(
    person_id: str,
    start_date: Optional[datetime] = Query(None, description="Filter events after this date"),
    end_date: Optional[datetime] = Query(None, description="Filter events before this date"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get chronological timeline of events for a specific person.
    
    Example:
    GET /api/events/person/opentrace.org/person/namus.MP24398/timeline
    """
    try:
        if db is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database not configured")

        # Verify person exists
        person_result = await db.execute(
            select(Person).where(Person.pfif_id == person_id)
        )
        if not person_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Person with pfif_id '{person_id}' not found"
            )

        # Build query
        query = select(Event).where(
            Event.pfif_id == person_id,
            Event.is_public == True  # Only show public events in timeline
        )

        if start_date:
            query = query.where(Event.event_timestamp >= start_date)
        if end_date:
            query = query.where(Event.event_timestamp <= end_date)

        query = query.order_by(Event.event_timestamp)

        result = await db.execute(query)
        events = result.scalars().all()

        return {
            "person_id": person_id,
            "event_count": len(events),
            "timeline": [
                {
                    "event_id": str(event.event_id),
                    "name": event.name,
                    "event_type": event.event_type,
                    "event_timestamp": event.event_timestamp.isoformat() if event.event_timestamp else None,
                    "profile": event.profile,
                    "location_id": event.location_id,
                    "confidence_score": event.source_confidence,
                    "is_verified": event.is_verified
                }
                for event in events
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get person timeline",
            extra={"error": str(e), "person_id": person_id, "action": "timeline_error"}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get timeline: {str(e)}"
        )


@router.get("/location/{location_id}/events")
async def get_location_events(
    location_id: str,
    start_date: Optional[datetime] = Query(None, description="Filter events after this date"),
    end_date: Optional[datetime] = Query(None, description="Filter events before this date"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get all events associated with a specific location.
    
    Example:
    GET /api/events/location/los-angeles-ca-usa/events
    """
    try:
        if db is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database not configured")

        # Verify location exists
        location_result = await db.execute(
            select(Location).where(Location.location_id == location_id)
        )
        if not location_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Location with location_id '{location_id}' not found"
            )

        # Build query
        query = select(Event).where(
            Event.location_id == location_id,
            Event.is_public == True
        )

        if start_date:
            query = query.where(Event.event_timestamp >= start_date)
        if end_date:
            query = query.where(Event.event_timestamp <= end_date)

        query = query.order_by(desc(Event.event_timestamp))

        # Get total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await db.execute(query)
        events = result.scalars().all()

        return {
            "location_id": location_id,
            "event_count": len(events),
            "total": total,
            "page": page,
            "page_size": page_size,
            "events": [
                {
                    "event_id": str(event.event_id),
                    "name": event.name,
                    "event_type": event.event_type,
                    "event_timestamp": event.event_timestamp.isoformat() if event.event_timestamp else None,
                    "profile": event.profile,
                    "person_id": event.pfif_id,
                    "confidence_score": event.source_confidence,
                    "is_verified": event.is_verified
                }
                for event in events
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get location events",
            extra={"error": str(e), "location_id": location_id, "action": "location_events_error"}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get location events: {str(e)}"
        )


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: str,
    db: AsyncSession = Depends(get_db_session),
    admin: AdminUser = Depends(require_admin_role("admin"))
):
    """
    Delete an event (soft delete only for audit integrity).
    
    Note: Events are append-only for audit integrity.
    Deletion is restricted to admin users and creates an audit log.
    
    Example:
    DELETE /api/events/550e8400-e29b-41d4-a716-446655440000
    """
    try:
        if db is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database not configured")

        result = await db.execute(
            select(Event).where(Event.event_id == event_id)
        )
        event = result.scalar_one_or_none()

        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event with id '{event_id}' not found"
            )

        # Soft delete: hide from public view
        event.is_public = False
        event.is_verified = False

        await db.commit()

        logger.info(
            "Event soft-deleted (marked private)",
            extra={
                "event_id": event_id,
                "action": "event_soft_delete"
            }
        )

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to delete event",
            extra={"error": str(e), "event_id": event_id, "action": "event_delete_error"}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete event: {str(e)}"
        )


@router.patch("/{event_id}/verify", response_model=EventResponse)
async def verify_event(
    event_id: str,
    verified_status: str = Query(..., description="New verification status: verified, disputed, pending, unverified"),
    db: AsyncSession = Depends(get_db_session),
    admin: AdminUser = Depends(require_admin_role("admin"))
):
    """
    Update the verification status of an event.

    This is the only allowed update operation for events (immutability constraint).
    Verification status does not alter the event data itself.

    Example:
    PATCH /api/events/550e8400-e29b-41d4-a716-446655440000/verify?verified_status=verified
    """
    try:
        valid_statuses = ["unverified", "pending", "verified", "disputed"]
        if verified_status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid verification status. Must be one of: {', '.join(valid_statuses)}"
            )
        if db is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database not configured")

        result = await db.execute(
            select(Event).where(Event.event_id == event_id)
        )
        event = result.scalar_one_or_none()

        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event with id '{event_id}' not found"
            )

        event.is_verified = True if verified_status == "verified" else False
        await db.commit()
        await db.refresh(event)

        logger.info(
            "Event verification updated",
            extra={
                "event_id": event_id,
                "new_status": verified_status,
                "action": "event_verify"
            }
        )

        return EventResponse(
            event_id=str(event.event_id),
            name=event.name,
            event_type=event.event_type,
            event_timestamp=event.event_timestamp.isoformat() if event.event_timestamp else None,
            profile=event.profile,
            person_id=event.pfif_id,
            location_id=event.location_id,
            confidence_score=event.source_confidence,
            is_verified=event.is_verified,
            is_public=event.is_public,
            created_at=event.created_at.isoformat() if event.created_at else None,
            source_type=event.source_type,
            source_url=event.source_url
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to verify event",
            extra={"error": str(e), "event_id": event_id, "action": "event_verify_error"}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify event: {str(e)}"
        )
