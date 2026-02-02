# models/source.py
"""
Source Entity - Provenance and data lineage model for Opentrace
Centralizes all data sources (user reports, APIs, sensors, scrapers) into a canonical registry.
Enables trust-aware querying and provenance tracking across the traceability graph.
"""

from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, Numeric, Index, CheckConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from uuid import uuid4
from typing import Optional, Dict, Any
from datetime import datetime

Base = declarative_base()


class Source(Base):
    """
    Canonical Source entity representing data provenance and lineage.
    
    This table centralizes all sources of information in the Open Trace system:
    - User reports and submissions
    - External APIs (NamUs, Interpol, etc.)
    - Automated scrapers and importers
    - IoT sensors and automated systems
    - Manual admin entries
    
    Each Event, Person, Location, or IntelItem can be linked to a Source,
    enabling trust-aware querying and complete provenance tracking.
    """
    __tablename__ = "source"

    # Stable identifier (UUID-based, like event_id)
    source_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4,
                      index=True,
                      comment="Globally unique identifier for this source")
    
    # Source identification
    source_name = Column(String(255), nullable=False, unique=True, index=True,
                        comment="Human-readable name: 'NamUs API', 'User Report Portal'")
    source_code = Column(String(50), nullable=False, unique=True, index=True,
                        comment="Short code: 'namus', 'user_portal', 'sensor_001'")
    
    # Source classification
    source_type = Column(String(50), nullable=False, index=True,
                        comment="api, user_report, scraper, sensor, manual, system")
    source_category = Column(String(50), nullable=False,
                            comment="official, community, automated, verified, unverified")
    
    # Source metadata
    description = Column(Text,
                        comment="Detailed description of the source and its purpose")
    organization = Column(String(255),
                         comment="Organization operating this source: 'FBI', 'Reddit', 'IoT Sensor Network'")
    jurisdiction = Column(String(100),
                         comment="Geographic or legal jurisdiction: 'US-Federal', 'EU', 'Global'")
    
    # Contact and URL information
    source_url = Column(String(1000), comment="Primary URL or endpoint for this source")
    contact_email = Column(String(255), comment="Contact email for source issues")
    documentation_url = Column(String(1000), comment="API docs or source documentation")
    
    # Reliability and trust scoring
    reliability_score = Column(Numeric(3, 2), default=0.7,
                              comment="0.0-1.0 automated reliability score based on history")
    trust_tier = Column(String(20), default="standard",
                       comment="verified, trusted, standard, community, unverified")
    verification_status = Column(String(20), default="unverified",
                                comment="verified, pending, unverified, suspended, deprecated")
    
    # Source capabilities and metadata
    data_types = Column(JSONB,
                       comment="JSON array of data types provided: ['person', 'location', 'event', 'intel']")
    api_config = Column(JSONB,
                       comment="API configuration (for api type sources): keys, rate limits, endpoints")
    source_metadata = Column(JSONB,
                            comment="Flexible metadata for source-specific attributes")
    
    # Operational status
    is_active = Column(Boolean, default=True, index=True,
                      comment="Source is currently operational and accepting data")
    last_successful_fetch = Column(DateTime(timezone=True),
                                  comment="Last successful data fetch from this source")
    last_failed_fetch = Column(DateTime(timezone=True),
                              comment="Last failed data fetch attempt")
    error_count = Column(Integer, default=0,
                        comment="Consecutive error count for automated sources")
    
    # Rate limiting and quotas
    rate_limit_per_hour = Column(Integer,
                                comment="API rate limit: requests per hour (NULL = unlimited)")
    rate_limit_per_day = Column(Integer,
                               comment="API rate limit: requests per day (NULL = unlimited)")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False,
                       comment="When this source was registered")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
                       comment="Last update to source configuration")
    
    # Audit
    created_by = Column(String(100), comment="User or system that registered this source")
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_source_code', 'source_code'),
        Index('idx_source_type', 'source_type'),
        Index('idx_source_category', 'source_category'),
        Index('idx_source_active', 'is_active'),
        Index('idx_source_trust', 'trust_tier'),
        Index('idx_source_verification', 'verification_status'),
        Index('idx_source_reliability', 'reliability_score'),
        Index('idx_source_data_types', 'data_types', postgresql_using='gin'),
        # Check constraints for data integrity
        CheckConstraint(source_type.in_([
            'api', 'user_report', 'scraper', 'sensor', 'manual', 'system', 'import'
        ]), name='valid_source_type'),
        CheckConstraint(source_category.in_([
            'official', 'community', 'automated', 'verified', 'unverified', 'sandbox'
        ]), name='valid_source_category'),
        CheckConstraint(trust_tier.in_([
            'verified', 'trusted', 'standard', 'community', 'unverified', 'blocked'
        ]), name='valid_trust_tier'),
        CheckConstraint(verification_status.in_([
            'verified', 'pending', 'unverified', 'suspended', 'deprecated', 'revoked'
        ]), name='valid_verification_status'),
        CheckConstraint(reliability_score >= 0.0, name='reliability_min'),
        CheckConstraint(reliability_score <= 1.0, name='reliability_max'),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.trust_tier is None:
            self.trust_tier = "standard"
        if self.reliability_score is None:
            self.reliability_score = 0.7
        if self.verification_status is None:
            self.verification_status = "unverified"
        if self.is_active is None:
            self.is_active = True

    def __repr__(self):
        return f"<Source(source_id='{self.source_id}', code='{self.source_code}', name='{self.source_name}')>"

    @property
    def display_name(self) -> str:
        """Return best available display name."""
        if self.source_name:
            return self.source_name
        return self.source_code

    @property
    def is_reliable(self) -> bool:
        """Check if source meets reliability threshold."""
        if not self.reliability_score:
            return False
        return float(self.reliability_score) >= 0.5

    @property
    def is_verified_source(self) -> bool:
        """Check if source is verified."""
        return self.verification_status == "verified"

    @property
    def health_status(self) -> str:
        """Return health status based on errors and last fetch."""
        if not self.is_active:
            return "inactive"
        if self.error_count and self.error_count > 5:
            return "unhealthy"
        if self.last_failed_fetch and self.last_successful_fetch:
            if self.last_failed_fetch > self.last_successful_fetch:
                return "degraded"
        return "healthy"

    @property
    def rate_limit_display(self) -> str:
        """Return human-readable rate limit info."""
        if self.rate_limit_per_hour:
            return f"{self.rate_limit_per_hour}/hour"
        if self.rate_limit_per_day:
            return f"{self.rate_limit_per_day}/day"
        return "unlimited"

    def to_public_dict(self) -> Dict[str, Any]:
        """Return safe public representation."""
        return {
            "source_id": str(self.source_id),
            "source_name": self.source_name,
            "source_code": self.source_code,
            "source_type": self.source_type,
            "source_category": self.source_category,
            "description": self.description,
            "organization": self.organization,
            "jurisdiction": self.jurisdiction,
            "source_url": self.source_url,
            "trust_tier": self.trust_tier,
            "verification_status": self.verification_status,
            "reliability_score": float(self.reliability_score) if self.reliability_score else None,
            "data_types": self.data_types or [],
            "is_active": self.is_active,
            "health_status": self.health_status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def to_admin_dict(self) -> Dict[str, Any]:
        """Return full representation for admin use."""
        return {
            "source_id": str(self.source_id),
            "source_name": self.source_name,
            "source_code": self.source_code,
            "source_type": self.source_type,
            "source_category": self.source_category,
            "description": self.description,
            "organization": self.organization,
            "jurisdiction": self.jurisdiction,
            "source_url": self.source_url,
            "contact_email": self.contact_email,
            "documentation_url": self.documentation_url,
            "trust_tier": self.trust_tier,
            "verification_status": self.verification_status,
            "reliability_score": float(self.reliability_score) if self.reliability_score else None,
            "data_types": self.data_types or [],
            "api_config": self.api_config,
            "source_metadata": self.source_metadata,
            "is_active": self.is_active,
            "last_successful_fetch": self.last_successful_fetch.isoformat() if self.last_successful_fetch else None,
            "last_failed_fetch": self.last_failed_fetch.isoformat() if self.last_failed_fetch else None,
            "error_count": self.error_count,
            "rate_limit_per_hour": self.rate_limit_per_hour,
            "rate_limit_per_day": self.rate_limit_per_day,
            "health_status": self.health_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by
        }

    def to_provenance_dict(self) -> Dict[str, Any]:
        """Return minimal representation for provenance tracking."""
        return {
            "source_id": str(self.source_id),
            "source_code": self.source_code,
            "source_name": self.source_name,
            "trust_tier": self.trust_tier,
            "verification_status": self.verification_status,
            "reliability_score": float(self.reliability_score) if self.reliability_score else None
        }
