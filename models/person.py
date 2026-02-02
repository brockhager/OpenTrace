# models/person.py
"""
Person Entity - Core identity model for Opentrace
Serves as the single source of truth for all missing, unidentified, and found individuals.
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, ARRAY, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class Person(Base):
    """
    Canonical Person entity representing missing, unidentified, or found individuals.
    
    This table replaces fragmented profile tables with a normalized schema that
    supports identity resolution, longitudinal tracking, and stable public references.
    """
    __tablename__ = "person"

    # Stable public identifier (PFIF-compliant)
    pfif_id = Column(String, primary_key=True, index=True, 
                     comment="e.g., opentrace.org/person/namus.MP24398")
    
    # Core identity fields (nullable - some sources only have partial info)
    given_name = Column(String, comment="First name")
    family_name = Column(String, comment="Last name")
    alternate_names = Column(ARRAY(String), comment="Aliases, nicknames, maiden names")
    
    # Demographics
    age_at_disappearance = Column(Integer, comment="Age when person went missing")
    sex = Column(String, comment="Male, Female, Unknown")
    
    # Status and timing
    status = Column(String, default="missing", 
                   comment="missing, unidentified, found")
    date_last_seen = Column(DateTime, comment="Date person was last seen")
    date_reported = Column(DateTime, comment="Date case was officially reported")
    
    # Data quality and workflow
    is_confirmed = Column(Boolean, default=False, 
                         comment="True = verified by moderator, False = pending review")
    source_confidence = Column(String, default="medium", 
                              comment="high, medium, low - based on source reliability")
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(),
                       comment="When this record was created in Opentrace")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), 
                       onupdate=func.now(),
                       comment="Last update timestamp")
    entry_date = Column(DateTime(timezone=True), server_default=func.now(),
                        comment="Original entry date from source")
    
    # Source tracking (minimal - details in intel_item)
    primary_source = Column(String, comment="Primary data source: namus, interpol, charley, pdf, etc.")
    source_id = Column(String, comment="Original ID from source system")
    source_url = Column(Text, comment="Link to original source record")
    
    # Privacy and compliance
    is_active = Column(Boolean, default=True,
                      comment="Soft-delete flag for GDPR compliance")
    data_sensitivity = Column(String, default="standard",
                            comment="standard, sensitive, restricted - affects access controls")

    def __repr__(self):
        return f"<Person(pfif_id='{self.pfif_id}', name='{self.given_name} {self.family_name}')>"

    @property
    def display_name(self):
        """Return best available name for display purposes."""
        if self.given_name and self.family_name:
            return f"{self.given_name} {self.family_name}"
        elif self.given_name:
            return self.given_name
        elif self.family_name:
            return self.family_name
        else:
            return "Unnamed Person"

    @property
    def age_display(self):
        """Return age in human-readable format."""
        if self.age_at_disappearance:
            return f"{self.age_at_disappearance} years old"
        return "Age unknown"

    def to_public_dict(self):
        """Return safe public representation (excludes sensitive fields)."""
        return {
            "pfif_id": self.pfif_id,
            "given_name": self.given_name,
            "family_name": self.family_name,
            "age_at_disappearance": self.age_at_disappearance,
            "sex": self.sex,
            "status": self.status,
            "date_last_seen": self.date_last_seen.isoformat() if self.date_last_seen else None,
            "primary_source": self.primary_source,
            # Include source_url for public detail pages so users can follow the original record/tip line
            "source_url": self.source_url
        }

    def to_admin_dict(self):
        """Return full representation for admin use."""
        return {
            "pfif_id": self.pfif_id,
            "given_name": self.given_name,
            "family_name": self.family_name,
            "alternate_names": self.alternate_names,
            "age_at_disappearance": self.age_at_disappearance,
            "sex": self.sex,
            "status": self.status,
            "date_last_seen": self.date_last_seen.isoformat() if self.date_last_seen else None,
            "date_reported": self.date_reported.isoformat() if self.date_reported else None,
            "is_confirmed": self.is_confirmed,
            "source_confidence": self.source_confidence,
            "primary_source": self.primary_source,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_active": self.is_active,
            "data_sensitivity": self.data_sensitivity
        }
