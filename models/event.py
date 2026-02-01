# models/event.py
"""
Event Entity - Temporal interaction model for Opentrace
Captures all temporal interactions and status changes in the missing persons ecosystem.
Creates complete chronological timelines for each person's journey through the system.
"""

from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, Numeric, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from uuid import uuid4
from typing import Optional, Dict, Any, List
from datetime import datetime

Base = declarative_base()


class Event(Base):
    """
    Event entity representing temporal interactions and status changes.
    
    This table captures every interaction with a missing person case:
    sightings, police reports, community tips, status changes, document submissions,
    and other temporal events that create a complete timeline.
    """
    __tablename__ = "event"

    # Stable identifier
    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4,
                      comment="Unique identifier for this event")
    
    # Entity relationships
    pfif_id = Column(String(255), nullable=False, index=True,
                     comment="Reference to person.pfif_id")
    location_id = Column(String(100), index=True,
                        comment="Reference to location.location_id (optional)")
    
    # Event classification
    event_type = Column(String(50), nullable=False, index=True,
                        comment="sighting, police_report, status_change, tip, document, recovery")
    event_subtype = Column(String(50), index=True,
                         comment="witness_report, anonymous_tip, family_report, digital_trace, etc.")
    
    # Temporal data
    event_date = Column(DateTime(timezone=True), nullable=False, index=True,
                       comment="When the event occurred (actual time)")
    event_timestamp = Column(DateTime(timezone=True), nullable=False, index=True,
                            comment="ISO 8601 timestamp of event occurrence (traceability model, mirrors event_date)")
    reported_date = Column(DateTime(timezone=True), nullable=False, index=True,
                         comment="When this event was reported to system")
    
    # Event content
    name = Column(String(500), comment="Human-readable label: Departure, Inspection, Handover (traceability model)")
    title = Column(String(500), comment="Brief event title for quick scanning")
    description = Column(Text, comment="Detailed event description")
    summary = Column(Text, comment="AI-generated summary for quick scanning")
    
    # Profile: structured metadata for traceability model
    profile = Column(JSONB, comment="Structured metadata describing event details (traceability model)")
    
    # Source and verification (Phase 16: Source entity provenance tracking)
    source_id = Column(UUID(as_uuid=True), 
                      comment="Reference to source.source_id for provenance tracking (Phase 16)")
    source_type = Column(String(50), nullable=False, index=True,
                        comment="user_submitted, police_report, scraper, system_generated, media_report (legacy, prefer source_id)")
    source_url = Column(String(500), comment="Original source URL or reference (legacy, prefer source_id)")
    source_confidence = Column(String(20), default="medium", index=True,
                              comment="high, medium, low - based on source reliability")
    is_verified = Column(Boolean, default=False, index=True,
                       comment="Verified by moderator or authority")
    
    # Evidence and attachments
    evidence_count = Column(Integer, default=0, index=True,
                           comment="Number of attached photos, documents, etc.")
    has_media = Column(Boolean, default=False, index=True,
                     comment="True if event has photos/audio/video")
    
    # Geographic context
    location_description = Column(String(500),
                               comment="Free text location if no canonical location")
    location_precision = Column(String(20), default="unknown",
                               comment="exact, approximate, estimated, unknown")
    
    # People involved
    reporter_name = Column(String(200), comment="Name of person reporting (if public)")
    reporter_contact = Column(String(500), comment="Contact info (if public)")
    witness_count = Column(Integer, default=0, comment="Number of witnesses")
    
    # Status and workflow
    event_status = Column(String(20), default="active", index=True,
                        comment="active, resolved, false_alarm, duplicate, archived")
    priority = Column(String(20), default="medium", index=True,
                    comment="low, medium, high, critical")
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True,
                       comment="When this event was created in system")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
                       comment="Last update timestamp")
    created_by = Column(String(100), comment="User or system that created event")
    tags = Column(ARRAY(String), comment="Tags for categorization and search")
    
    # AI processing
    ai_processed = Column(Boolean, default=False, index=True,
                       comment="True if AI has processed this event")
    ai_confidence = Column(Numeric(3, 2), comment="AI confidence in classification (0.0-1.0)")
    ai_entities = Column(JSONB, comment="Entities extracted by AI (names, locations, dates)")
    ai_sentiment = Column(String(20), comment="sentiment analysis: positive, negative, neutral")
    
    # Privacy and access
    is_public = Column(Boolean, default=True, index=True,
                      comment="False = law enforcement only")
    access_level = Column(String(20), default="public",
                         comment="public, law_enforcement, admin, restricted")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_event_pfif_id', 'pfif_id'),
        Index('idx_event_location_id', 'location_id'),
        Index('idx_event_type_date', 'event_type', 'event_date'),
        Index('idx_event_status', 'event_status'),
        Index('idx_event_priority', 'priority'),
        Index('idx_event_created', 'created_at'),
        Index('idx_event_verified', 'is_verified'),
        Index('idx_event_public', 'is_public'),
        Index('idx_event_source_type', 'source_type'),
        Index('idx_event_composite', 'pfif_id', 'event_date', 'event_status'),
        Index('idx_event_source_id', 'source_id'),  # Phase 16: Source provenance tracking
    )

    def __repr__(self):
        return f"<Event(event_id='{self.event_id}', type='{self.event_type}', pfif_id='{self.pfif_id}')>"

    @property
    def display_title(self) -> str:
        """Return best available title for display."""
        if self.title:
            return self.title
        elif self.summary:
            return self.summary[:100] + "..." if len(self.summary) > 100 else self.summary
        elif self.description:
            return self.description[:100] + "..." if len(self.description) > 100 else self.description
        else:
            return f"{self.event_type.replace('_', ' ').title()} Event"

    @property
    def time_elapsed(self) -> str:
        """Return human-readable time elapsed since event."""
        if not self.event_date:
            return "Unknown time"
        
        now = datetime.utcnow()
        delta = now - self.event_date.replace(tzinfo=None)
        
        if delta.days > 365:
            years = delta.days // 365
            return f"{years} year{'s' if years != 1 else ''} ago"
        elif delta.days > 30:
            months = delta.days // 30
            return f"{months} month{'s' if months != 1 else ''} ago"
        elif delta.days > 0:
            return f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            return "Just now"

    @property
    def confidence_level(self) -> str:
        """Return confidence level based on source and verification."""
        if self.is_verified:
            return "verified"
        elif self.source_confidence == "high":
            return "high"
        elif self.source_confidence == "medium":
            return "medium"
        else:
            return "low"

    def get_event_color(self) -> str:
        """Return color code for event type (for UI display)."""
        colors = {
            'sighting': '#34a853',      # Green
            'police_report': '#4285f4',  # Blue
            'status_change': '#fbbc04', # Yellow
            'tip': '#ea4335',           # Red
            'document': '#9e9e9e',       # Gray
            'recovery': '#34a853',       # Green
            'false_alarm': '#9e9e9e',    # Gray
            'digital_trace': '#ff6d00'   # Orange
        }
        return colors.get(self.event_type, '#9e9e9e')

    def to_public_dict(self) -> Dict[str, Any]:
        """Return safe public representation."""
        return {
            "event_id": str(self.event_id),
            "pfif_id": self.pfif_id,
            "person_id": self.pfif_id,  # Alias for traceability model
            "event_type": self.event_type,
            "event_subtype": self.event_subtype,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "event_timestamp": self.event_timestamp.isoformat() if self.event_timestamp else None,
            "name": self.name,
            "title": self.title,
            "summary": self.summary,
            "description": self.description if self.is_public else "Restricted content",
            "profile": self.profile if self.is_public else None,
            "source_id": str(self.source_id) if self.source_id else None,
            "source_type": self.source_type,
            "source_confidence": self.source_confidence,
            "is_verified": self.is_verified,
            "evidence_count": self.evidence_count,
            "has_media": self.has_media,
            "location_id": self.location_id,
            "location_description": self.location_description if self.is_public else None,
            "location_precision": self.location_precision,
            "reporter_name": self.reporter_name if self.is_public else None,
            "witness_count": self.witness_count,
            "event_status": self.event_status,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "time_elapsed": self.time_elapsed,
            "confidence_level": self.confidence_level,
            "tags": self.tags or [],
            "ai_processed": self.ai_processed,
            "ai_sentiment": self.ai_sentiment
        }

    def to_admin_dict(self) -> Dict[str, Any]:
        """Return full representation for admin use."""
        return {
            "event_id": str(self.event_id),
            "pfif_id": self.pfif_id,
            "person_id": self.pfif_id,  # Alias for traceability model
            "location_id": self.location_id,
            "event_type": self.event_type,
            "event_subtype": self.event_subtype,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "event_timestamp": self.event_timestamp.isoformat() if self.event_timestamp else None,
            "reported_date": self.reported_date.isoformat() if self.reported_date else None,
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "summary": self.summary,
            "profile": self.profile,
            "source_id": str(self.source_id) if self.source_id else None,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "source_confidence": self.source_confidence,
            "is_verified": self.is_verified,
            "evidence_count": self.evidence_count,
            "has_media": self.has_media,
            "location_description": self.location_description,
            "location_precision": self.location_precision,
            "reporter_name": self.reporter_name,
            "reporter_contact": self.reporter_contact,
            "witness_count": self.witness_count,
            "event_status": self.event_status,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "tags": self.tags or [],
            "is_public": self.is_public,
            "access_level": self.access_level,
            "ai_processed": self.ai_processed,
            "ai_confidence": float(self.ai_confidence) if self.ai_confidence else None,
            "ai_entities": self.ai_entities,
            "ai_sentiment": self.ai_sentiment,
            "time_elapsed": self.time_elapsed,
            "confidence_level": self.confidence_level
        }

    def to_timeline_dict(self) -> Dict[str, Any]:
        """Return representation optimized for timeline display."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "event_subtype": self.event_subtype,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "title": self.display_title,
            "description": self.description if self.is_public else "Restricted content",
            "location_description": self.location_description,
            "is_verified": self.is_verified,
            "evidence_count": self.evidence_count,
            "has_media": self.has_media,
            "source_type": self.source_type,
            "confidence_level": self.confidence_level,
            "priority": self.priority,
            "color": self.get_event_color(),
            "time_elapsed": self.time_elapsed
        }
