# models/event_evidence.py
"""
Event Evidence Model - Attachments and evidence for events
Handles photos, videos, documents, and other evidence attached to events.
"""

from sqlalchemy import Column, String, Boolean, Text, BigInteger, Integer, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4
from typing import Optional, Dict, Any
from datetime import datetime

Base = declarative_base()


class EventEvidence(Base):
    """
    Evidence and attachments for events.
    
    This table stores all evidence files attached to events:
    - Photos and videos from sightings
    - Documents and PDFs from submissions
    - Audio recordings of witness statements
    - Screenshots and digital evidence
    """
    __tablename__ = "event_evidence"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Relationship to event
    event_id = Column(UUID(as_uuid=True), nullable=False, index=True,
                      comment="Reference to event.event_id")
    
    # Evidence metadata
    evidence_type = Column(String(50), nullable=False, index=True,
                          comment="photo, video, audio, document, screenshot, text, url")
    file_name = Column(String(500), comment="Original filename")
    file_size = Column(BigInteger, comment="File size in bytes")
    mime_type = Column(String(100), comment="MIME type")
    file_hash = Column(String(64), index=True, comment="SHA-256 hash for deduplication")
    
    # Storage information
    storage_url = Column(String(1000), comment="Cloud storage URL")
    thumbnail_url = Column(String(1000), comment="Thumbnail URL for images/videos")
    preview_url = Column(String(1000), comment="Preview URL for documents")
    
    # Content analysis
    description = Column(Text, comment="Description of evidence")
    extracted_text = Column(Text, comment="OCR or transcribed text")
    ai_analysis = Column(String(1000), comment="AI analysis results summary")
    ai_confidence = Column(String(20), comment="AI confidence in analysis")
    
    # Media-specific metadata
    width = Column(Integer, comment="Image/video width in pixels")
    height = Column(Integer, comment="Image/video height in pixels")
    duration = Column(Integer, comment="Video/audio duration in seconds")
    
    # Verification and processing
    is_verified = Column(Boolean, default=False, index=True,
                       comment="Verified by moderator or authority")
    verification_notes = Column(Text, comment="Notes from verification process")
    processing_status = Column(String(20), default="pending", index=True,
                             comment="pending, processing, completed, failed")
    
    # Privacy and access controls
    is_public = Column(Boolean, default=False, index=True,
                      comment="False = law enforcement only")
    access_level = Column(String(20), default="restricted", index=True,
                         comment="public, law_enforcement, admin, restricted")
    contains_pii = Column(Boolean, default=False, index=True,
                         comment="Contains personally identifiable information")
    
    # Source information
    source_type = Column(String(50), comment="user_upload, system_generated, scraper")
    source_url = Column(String(500), comment="Original source URL if applicable")
    uploaded_by = Column(String(100), comment="User who uploaded this evidence")
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True,
                       comment="When this evidence was uploaded")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
                       comment="Last update timestamp")
    tags = Column(String(500), comment="Comma-separated tags for categorization")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_evidence_event_id', 'event_id'),
        Index('idx_evidence_type', 'evidence_type'),
        Index('idx_evidence_file_hash', 'file_hash'),
        Index('idx_evidence_verified', 'is_verified'),
        Index('idx_evidence_public', 'is_public'),
        Index('idx_evidence_processing', 'processing_status'),
        Index('idx_evidence_contains_pii', 'contains_pii'),
        Index('idx_evidence_created', 'created_at'),
    )

    def __repr__(self):
        return f"<EventEvidence(id='{self.id}', type='{self.evidence_type}', event_id='{self.event_id}')>"

    @property
    def file_size_display(self) -> str:
        """Return human-readable file size."""
        if not self.file_size:
            return "Unknown size"
        
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    @property
    def is_image(self) -> bool:
        """Check if evidence is an image."""
        return self.mime_type and self.mime_type.startswith('image/')

    @property
    def is_video(self) -> bool:
        """Check if evidence is a video."""
        return self.mime_type and self.mime_type.startswith('video/')

    @property
    def is_audio(self) -> bool:
        """Check if evidence is audio."""
        return self.mime_type and self.mime_type.startswith('audio/')

    @property
    def is_document(self) -> bool:
        """Check if evidence is a document."""
        return self.mime_type and self.mime_type in [
            'application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain', 'text/csv'
        ]

    @property
    def display_type(self) -> str:
        """Return user-friendly type name."""
        type_names = {
            'photo': 'Photo',
            'video': 'Video', 
            'audio': 'Audio',
            'document': 'Document',
            'screenshot': 'Screenshot',
            'text': 'Text',
            'url': 'Link'
        }
        return type_names.get(self.evidence_type, self.evidence_type.title())

    @property
    def has_preview(self) -> bool:
        """Check if evidence has a preview available."""
        return bool(self.thumbnail_url or self.preview_url)

    @property
    def processing_complete(self) -> bool:
        """Check if processing is complete."""
        return self.processing_status == 'completed'

    def get_access_level_display(self) -> str:
        """Return user-friendly access level."""
        levels = {
            'public': 'Public',
            'law_enforcement': 'Law Enforcement Only',
            'admin': 'Admin Only',
            'restricted': 'Restricted Access'
        }
        return levels.get(self.access_level, self.access_level)

    def to_public_dict(self) -> Dict[str, Any]:
        """Return safe public representation."""
        result = {
            "id": str(self.id),
            "evidence_type": self.evidence_type,
            "display_type": self.display_type,
            "file_name": self.file_name,
            "file_size_display": self.file_size_display,
            "description": self.description,
            "is_verified": self.is_verified,
            "processing_status": self.processing_status,
            "processing_complete": self.processing_complete,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "access_level": self.get_access_level_display()
        }
        
        # Add media URLs if public
        if self.is_public:
            if self.thumbnail_url:
                result["thumbnail_url"] = self.thumbnail_url
            if self.preview_url:
                result["preview_url"] = self.preview_url
        
        return result

    def to_admin_dict(self) -> Dict[str, Any]:
        """Return full representation for admin use."""
        return {
            "id": str(self.id),
            "event_id": str(self.event_id),
            "evidence_type": self.evidence_type,
            "display_type": self.display_type,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "file_size_display": self.file_size_display,
            "mime_type": self.mime_type,
            "file_hash": self.file_hash,
            "storage_url": self.storage_url,
            "thumbnail_url": self.thumbnail_url,
            "preview_url": self.preview_url,
            "description": self.description,
            "extracted_text": self.extracted_text,
            "ai_analysis": self.ai_analysis,
            "ai_confidence": self.ai_confidence,
            "width": self.width,
            "height": self.height,
            "duration": self.duration,
            "is_verified": self.is_verified,
            "verification_notes": self.verification_notes,
            "processing_status": self.processing_status,
            "is_public": self.is_public,
            "access_level": self.access_level,
            "contains_pii": self.contains_pii,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "uploaded_by": self.uploaded_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "tags": self.tags.split(',') if self.tags else [],
            "is_image": self.is_image,
            "is_video": self.is_video,
            "is_audio": self.is_audio,
            "is_document": self.is_document,
            "has_preview": self.has_preview,
            "processing_complete": self.processing_complete
        }
