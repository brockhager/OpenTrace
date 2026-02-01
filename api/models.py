# models.py
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    CheckConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(AsyncAttrs, DeclarativeBase):
    pass


class PersonProfile(Base):
    __tablename__ = "person_profile"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    pfif_id = Column(String, unique=True, nullable=False, index=True)
    entry_date = Column(DateTime, default=datetime.utcnow)
    source_url = Column(String)  # e.g., NamUs case URL
    author_name = Column(String, default="Community")
    given_name = Column(String)
    family_name = Column(String)
    alternate_names = Column(ARRAY(String))  # e.g., ["Johnny", "J.D."]
    age = Column(Integer)
    sex = Column(String)
    last_seen_location = Column(String)
    status = Column(String, default="missing")
    is_confirmed = Column(Boolean, default=False)
    expiry_date = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(days=365))
    source_date = Column(String)  # From PFIF; often a date string like "2023-05-12"
    profile_url = Column(String)  # Direct link to source (NamUs, Interpol, etc.)

    # Relationships
    intel_items = relationship(
        "IntelItem",
        back_populates="profile",
        cascade="all, delete-orphan",  # Supports GDPR CASCADE via ORM
        passive_deletes=True,
    )
    links = relationship(
        "ProfileLink",
        back_populates="profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint(status.in_(["missing", "unidentified", "found"]), name="valid_status"),
    )


class IntelItem(Base):
    __tablename__ = "intel_item"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    person_pfif_id = Column(
        String, ForeignKey("person_profile.pfif_id", ondelete="CASCADE"), nullable=True
    )
    entry_date = Column(DateTime, default=datetime.utcnow)
    author_name = Column(String)  # Anonymous submitter ID (e.g., hashed IP)
    source_url = Column(String, nullable=False)  # Required per OSINT policy
    text = Column(Text)
    category = Column(String)
    confidence_rating = Column(String, default="low")
    reviewed = Column(Boolean, default=False)

    # Relationships
    profile = relationship("PersonProfile", back_populates="intel_items")
    links = relationship(
        "ProfileLink",
        back_populates="intel_item",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint(
            category.in_(["photo", "social_profile", "sighting", "associate"]),
            name="valid_category",
        ),
        CheckConstraint(
            confidence_rating.in_(["low", "medium", "high"]), name="valid_confidence"
        ),
        Index("ix_intel_unreviewed", reviewed, postgresql_where=(reviewed.is_(False))),
    )


class ProfileLink(Base):
    __tablename__ = "profile_link"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    intel_id = Column(
        UUID(as_uuid=True), ForeignKey("intel_item.id", ondelete="CASCADE"), nullable=False
    )
    profile_id = Column(
        UUID(as_uuid=True), ForeignKey("person_profile.id", ondelete="CASCADE"), nullable=False
    )
    decision = Column(String, nullable=False)  # confirmed, rejected, duplicate
    justification = Column(Text)

    # Relationships
    intel_item = relationship("IntelItem", back_populates="links")
    profile = relationship("PersonProfile", back_populates="links")

    __table_args__ = (
        CheckConstraint(
            decision.in_(["confirmed", "rejected", "duplicate"]), name="valid_decision"
        ),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    action = Column(String, nullable=False)  # e.g., "create_profile", "approve_intel"
    actor_id = Column(String)  # Admin ID or system
    target_id = Column(UUID(as_uuid=True))  # ID of affected record
    timestamp = Column(DateTime, default=datetime.utcnow)
    details = Column(JSON)  # Structured context (e.g., {"old_status": "missing", "new_status": "found"})

    __table_args__ = (Index("ix_audit_target", target_id),)