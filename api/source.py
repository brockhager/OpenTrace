# api/source.py
"""
Source API endpoints for Opentrace
Provides CRUD operations for the Source entity (provenance and data lineage).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, and_, or_
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID

from db.session import get_db_session
from auth.deps import require_admin_role
from auth.models import AdminUser
from models.source import Source
from core.logger import logger

router = APIRouter(prefix="/api/sources", tags=["sources"])


# Pydantic request/response models
class SourceCreateRequest(BaseModel):
    """Request model for creating a new source."""
    source_name: str = Field(..., max_length=255, description="Human-readable name")
    source_code: str = Field(..., max_length=50, description="Unique short code")
    source_type: str = Field(..., description="api, user_report, scraper, sensor, manual, system, import")
    source_category: str = Field(..., description="official, community, automated, verified, unverified, sandbox")
    description: Optional[str] = Field(None, description="Detailed description")
    organization: Optional[str] = Field(None, max_length=255, description="Operating organization")
    jurisdiction: Optional[str] = Field(None, max_length=100, description="Geographic/legal jurisdiction")
    source_url: Optional[str] = Field(None, description="Primary URL or endpoint")
    contact_email: Optional[str] = Field(None, description="Contact email")
    documentation_url: Optional[str] = Field(None, description="API documentation URL")
    trust_tier: Optional[str] = Field("standard", description="verified, trusted, standard, community, unverified, blocked")
    verification_status: Optional[str] = Field("unverified", description="verified, pending, unverified, suspended, deprecated, revoked")
    reliability_score: Optional[float] = Field(0.7, ge=0.0, le=1.0, description="0.0-1.0 reliability score")
    data_types: Optional[List[str]] = Field(None, description="Data types provided: person, location, event, intel")
    api_config: Optional[dict] = Field(None, description="API configuration for api type sources")
    source_metadata: Optional[dict] = Field(None, description="Flexible source metadata")
    is_active: Optional[bool] = Field(True, description="Source is operational")
    rate_limit_per_hour: Optional[int] = Field(None, description="Rate limit per hour")
    rate_limit_per_day: Optional[int] = Field(None, description="Rate limit per day")
    
    class Config:
        json_schema_extra = {
            "example": {
                "source_name": "NamUs API",
                "source_code": "namus_api",
                "source_type": "api",
                "source_category": "official",
                "description": "National Missing and Unidentified Persons System API",
                "organization": "US Department of Justice",
                "source_url": "https://www.namus.gov/api",
                "trust_tier": "verified",
                "verification_status": "verified",
                "reliability_score": 0.95,
                "data_types": ["person", "location"]
            }
        }


class SourceUpdateRequest(BaseModel):
    """Request model for updating a source."""
    source_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    organization: Optional[str] = Field(None, max_length=255)
    jurisdiction: Optional[str] = Field(None, max_length=100)
    source_url: Optional[str] = None
    contact_email: Optional[str] = None
    documentation_url: Optional[str] = None
    trust_tier: Optional[str] = None
    verification_status: Optional[str] = None
    reliability_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    data_types: Optional[List[str]] = None
    api_config: Optional[dict] = None
    source_metadata: Optional[dict] = None
    is_active: Optional[bool] = None
    rate_limit_per_hour: Optional[int] = None
    rate_limit_per_day: Optional[int] = None


class SourceResponse(BaseModel):
    """Response model for source data."""
    source_id: str
    source_name: str
    source_code: str
    source_type: str
    source_category: str
    description: Optional[str]
    organization: Optional[str]
    jurisdiction: Optional[str]
    source_url: Optional[str]
    trust_tier: str
    verification_status: str
    reliability_score: Optional[float]
    data_types: List[str]
    is_active: bool
    health_status: str
    created_at: str
    
    class Config:
        from_attributes = True


class SourceListResponse(BaseModel):
    """Response model for list of sources."""
    sources: List[SourceResponse]
    total: int
    page: int
    page_size: int


class SourceHealthUpdate(BaseModel):
    """Request model for updating source health status."""
    last_successful_fetch: Optional[datetime] = None
    last_failed_fetch: Optional[datetime] = None
    error_count: Optional[int] = None


@router.get("/health")
async def get_sources_health(db: AsyncSession = Depends(get_db_session)):
    """
    Get health status summary for all sources.
    
    Example:
    GET /api/sources/health
    """
    try:
        # Get counts by health status
        query = select(Source)
        result = await db.execute(query)
        sources = result.scalars().all()
        
        health_summary = {
            "healthy": 0,
            "degraded": 0,
            "unhealthy": 0,
            "inactive": 0,
            "total": len(sources)
        }
        
        for source in sources:
            status = source.health_status
            health_summary[status] = health_summary.get(status, 0) + 1
        
        return health_summary
        
    except Exception as e:
        logger.error(
            "Failed to get sources health",
            extra={"error": str(e), "action": "sources_health_error"}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get health status: {str(e)}"
        )


@router.get("/by-code/{source_code}", response_model=SourceResponse)
async def get_source_by_code(
    source_code: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get a specific source by its short code.
    
    Example:
    GET /api/sources/by-code/namus
    """
    try:
        result = await db.execute(
            select(Source).where(Source.source_code == source_code)
        )
        source = result.scalar_one_or_none()
        
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source with code '{source_code}' not found"
            )
        
        return SourceResponse(
            source_id=str(source.source_id),
            source_name=source.source_name,
            source_code=source.source_code,
            source_type=source.source_type,
            source_category=source.source_category,
            description=source.description,
            organization=source.organization,
            jurisdiction=source.jurisdiction,
            source_url=source.source_url,
            trust_tier=source.trust_tier,
            verification_status=source.verification_status,
            reliability_score=float(source.reliability_score) if source.reliability_score else None,
            data_types=source.data_types or [],
            is_active=source.is_active,
            health_status=source.health_status,
            created_at=source.created_at.isoformat() if source.created_at else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get source by code",
            extra={"error": str(e), "source_code": source_code, "action": "source_get_error"}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve source: {str(e)}"
        )


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    request: SourceCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    admin: AdminUser = Depends(require_admin_role("admin"))
):
    """
    Create a new source.
    
    Example:
    POST /api/sources
    {
        "source_name": "Custom Sensor Network",
        "source_code": "sensor_network_01",
        "source_type": "sensor",
        "source_category": "automated"
    }
    """
    try:
        # Check for duplicate source_code
        existing = await db.execute(
            select(Source).where(
                or_(Source.source_code == request.source_code,
                    Source.source_name == request.source_name)
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Source with code '{request.source_code}' or name '{request.source_name}' already exists"
            )
        
        # Create source
        source = Source(
            source_name=request.source_name,
            source_code=request.source_code,
            source_type=request.source_type,
            source_category=request.source_category,
            description=request.description,
            organization=request.organization,
            jurisdiction=request.jurisdiction,
            source_url=request.source_url,
            contact_email=request.contact_email,
            documentation_url=request.documentation_url,
            trust_tier=request.trust_tier,
            verification_status=request.verification_status,
            reliability_score=request.reliability_score,
            data_types=request.data_types,
            api_config=request.api_config,
            source_metadata=request.source_metadata,
            is_active=request.is_active,
            rate_limit_per_hour=request.rate_limit_per_hour,
            rate_limit_per_day=request.rate_limit_per_day,
            created_by=created_by
        )
        
        db.add(source)
        await db.commit()
        await db.refresh(source)
        
        logger.info(
            "Source created",
            extra={
                "source_id": str(source.source_id),
                "source_code": source.source_code,
                "action": "source_create"
            }
        )
        
        return SourceResponse(
            source_id=str(source.source_id),
            source_name=source.source_name,
            source_code=source.source_code,
            source_type=source.source_type,
            source_category=source.source_category,
            description=source.description,
            organization=source.organization,
            jurisdiction=source.jurisdiction,
            source_url=source.source_url,
            trust_tier=source.trust_tier,
            verification_status=source.verification_status,
            reliability_score=float(source.reliability_score) if source.reliability_score else None,
            data_types=source.data_types or [],
            is_active=source.is_active,
            health_status=source.health_status,
            created_at=source.created_at.isoformat() if source.created_at else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to create source",
            extra={"error": str(e), "action": "source_create_error"}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create source: {str(e)}"
        )


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get a specific source by ID.
    
    Example:
    GET /api/sources/550e8400-e29b-41d4-a716-446655440000
    """
    try:
        result = await db.execute(
            select(Source).where(Source.source_id == source_id)
        )
        source = result.scalar_one_or_none()
        
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source with id '{source_id}' not found"
            )
        
        return SourceResponse(
            source_id=str(source.source_id),
            source_name=source.source_name,
            source_code=source.source_code,
            source_type=source.source_type,
            source_category=source.source_category,
            description=source.description,
            organization=source.organization,
            jurisdiction=source.jurisdiction,
            source_url=source.source_url,
            trust_tier=source.trust_tier,
            verification_status=source.verification_status,
            reliability_score=float(source.reliability_score) if source.reliability_score else None,
            data_types=source.data_types or [],
            is_active=source.is_active,
            health_status=source.health_status,
            created_at=source.created_at.isoformat() if source.created_at else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get source",
            extra={"error": str(e), "source_id": source_id, "action": "source_get_error"}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve source: {str(e)}"
        )


@router.get("", response_model=SourceListResponse)
async def list_sources(
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    source_category: Optional[str] = Query(None, description="Filter by category"),
    trust_tier: Optional[str] = Query(None, description="Filter by trust tier"),
    verification_status: Optional[str] = Query(None, description="Filter by verification status"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    data_type: Optional[str] = Query(None, description="Filter by data type provided"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    List sources with optional filtering.
    
    Example:
    GET /api/sources?source_type=api&trust_tier=verified
    GET /api/sources?data_type=person&is_active=true
    """
    try:
        # Build query
        query = select(Source)
        
        # Apply filters
        if source_type:
            query = query.where(Source.source_type == source_type)
        if source_category:
            query = query.where(Source.source_category == source_category)
        if trust_tier:
            query = query.where(Source.trust_tier == trust_tier)
        if verification_status:
            query = query.where(Source.verification_status == verification_status)
        if is_active is not None:
            query = query.where(Source.is_active == is_active)
        if data_type:
            # Filter for sources that provide this data type
            query = query.where(Source.data_types.contains([data_type]))
        
        # Order by name
        query = query.order_by(Source.source_name)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        # Execute query
        result = await db.execute(query)
        sources = result.scalars().all()
        
        return SourceListResponse(
            sources=[
                SourceResponse(
                    source_id=str(source.source_id),
                    source_name=source.source_name,
                    source_code=source.source_code,
                    source_type=source.source_type,
                    source_category=source.source_category,
                    description=source.description,
                    organization=source.organization,
                    jurisdiction=source.jurisdiction,
                    source_url=source.source_url,
                    trust_tier=source.trust_tier,
                    verification_status=source.verification_status,
                    reliability_score=float(source.reliability_score) if source.reliability_score else None,
                    data_types=source.data_types or [],
                    is_active=source.is_active,
                    health_status=source.health_status,
                    created_at=source.created_at.isoformat() if source.created_at else None
                )
                for source in sources
            ],
            total=total,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(
            "Failed to list sources",
            extra={"error": str(e), "action": "source_list_error"}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sources: {str(e)}"
        )


@router.patch("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: str,
    request: SourceUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    admin: AdminUser = Depends(require_admin_role("admin"))
):
    """
    Update a source.
    
    Example:
    PATCH /api/sources/550e8400-e29b-41d4-a716-446655440000
    {
        "trust_tier": "verified",
        "reliability_score": 0.95
    }
    """
    try:
        result = await db.execute(
            select(Source).where(Source.source_id == source_id)
        )
        source = result.scalar_one_or_none()
        
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source with id '{source_id}' not found"
            )
        
        # Update fields
        update_data = request.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(source, field, value)
        
        await db.commit()
        await db.refresh(source)
        
        logger.info(
            "Source updated",
            extra={
                "source_id": source_id,
                "action": "source_update"
            }
        )
        
        return SourceResponse(
            source_id=str(source.source_id),
            source_name=source.source_name,
            source_code=source.source_code,
            source_type=source.source_type,
            source_category=source.source_category,
            description=source.description,
            organization=source.organization,
            jurisdiction=source.jurisdiction,
            source_url=source.source_url,
            trust_tier=source.trust_tier,
            verification_status=source.verification_status,
            reliability_score=float(source.reliability_score) if source.reliability_score else None,
            data_types=source.data_types or [],
            is_active=source.is_active,
            health_status=source.health_status,
            created_at=source.created_at.isoformat() if source.created_at else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to update source",
            extra={"error": str(e), "source_id": source_id, "action": "source_update_error"}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update source: {str(e)}"
        )


@router.patch("/{source_id}/health", response_model=SourceResponse)
async def update_source_health(
    source_id: str,
    request: SourceHealthUpdate,
    db: AsyncSession = Depends(get_db_session),
    admin: AdminUser = Depends(require_admin_role("admin"))
):
    """
    Update source health status (for automated monitoring).
    
    Example:
    PATCH /api/sources/550e8400-e29b-41d4-a716-446655440000/health
    {
        "last_successful_fetch": "2024-01-15T10:30:00Z",
        "error_count": 0
    }
    """
    try:
        result = await db.execute(
            select(Source).where(Source.source_id == source_id)
        )
        source = result.scalar_one_or_none()
        
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source with id '{source_id}' not found"
            )
        
        # Update health fields
        if request.last_successful_fetch is not None:
            source.last_successful_fetch = request.last_successful_fetch
        if request.last_failed_fetch is not None:
            source.last_failed_fetch = request.last_failed_fetch
        if request.error_count is not None:
            source.error_count = request.error_count
        
        await db.commit()
        await db.refresh(source)
        
        logger.info(
            "Source health updated",
            extra={
                "source_id": source_id,
                "health_status": source.health_status,
                "action": "source_health_update"
            }
        )
        
        return SourceResponse(
            source_id=str(source.source_id),
            source_name=source.source_name,
            source_code=source.source_code,
            source_type=source.source_type,
            source_category=source.source_category,
            description=source.description,
            organization=source.organization,
            jurisdiction=source.jurisdiction,
            source_url=source.source_url,
            trust_tier=source.trust_tier,
            verification_status=source.verification_status,
            reliability_score=float(source.reliability_score) if source.reliability_score else None,
            data_types=source.data_types or [],
            is_active=source.is_active,
            health_status=source.health_status,
            created_at=source.created_at.isoformat() if source.created_at else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to update source health",
            extra={"error": str(e), "source_id": source_id, "action": "source_health_error"}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update source health: {str(e)}"
        )


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: str,
    db: AsyncSession = Depends(get_db_session),
    admin: AdminUser = Depends(require_admin_role("admin"))
):
    """
    Soft delete a source (mark as deprecated).
    
    Example:
    DELETE /api/sources/550e8400-e29b-41d4-a716-446655440000
    """
    try:
        result = await db.execute(
            select(Source).where(Source.source_id == source_id)
        )
        source = result.scalar_one_or_none()
        
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source with id '{source_id}' not found"
            )
        
        # Soft delete - mark as deprecated and inactive
        source.is_active = False
        source.verification_status = "deprecated"
        
        await db.commit()
        
        logger.info(
            "Source deprecated",
            extra={
                "source_id": source_id,
                "action": "source_deprecate"
            }
        )
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to deprecate source",
            extra={"error": str(e), "source_id": source_id, "action": "source_delete_error"}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deprecate source: {str(e)}"
        )
