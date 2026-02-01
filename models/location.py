# models/location.py
"""
Location Entity - Canonical geographic model for Opentrace
Standardizes location data across all sources and enables spatial search capabilities.
"""

from sqlalchemy import Column, String, Numeric, DateTime, Boolean, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4
from typing import Optional, Dict, Any
import math

Base = declarative_base()


class Location(Base):
    """
    Canonical Location entity representing standardized geographic places.
    
    This table normalizes location data from multiple sources into a single
    canonical representation with coordinates, administrative boundaries,
    and confidence scoring.
    """
    __tablename__ = "location"

    # Stable identifier
    location_id = Column(String(100), primary_key=True, 
                         comment="Canonical ID: los-angeles-ca-usa, paris-75-fr")
    
    # Canonical place names
    canonical_name = Column(String(500), nullable=False,
                           comment="Los Angeles, California, USA")
    display_name = Column(String(200), nullable=False,
                         comment="Los Angeles, CA")
    short_name = Column(String(100),
                       comment="LA (optional abbreviation)")
    
    # Geographic coordinates (WGS84)
    latitude = Column(Numeric(10, 8), nullable=False,
                     comment="Decimal degrees: 34.052235")
    longitude = Column(Numeric(11, 8), nullable=False,
                      comment="Decimal degrees: -118.243683")
    coordinate_precision = Column(String(20), default="approximate",
                                 comment="exact, approximate, region, country")
    
    # Administrative hierarchy (ISO standards where possible)
    country_code = Column(String(2), nullable=False,
                         comment="ISO 3166-1 alpha-2: US, FR, GB")
    country_name = Column(String(100), nullable=False)
    admin1_code = Column(String(10), 
                         comment="ISO 3166-2: CA, TX, 75 (Île-de-France)")
    admin1_name = Column(String(100), 
                         comment="State/Province: California, Texas, Île-de-France")
    admin2_code = Column(String(20),
                         comment="FIPS: 06037 (Los Angeles County)")
    admin2_name = Column(String(100),
                         comment="County/District: Los Angeles County")
    locality = Column(String(100),
                      comment="City/Town: Los Angeles, Paris")
    
    # Location classification
    location_type = Column(String(50), nullable=False,
                          comment="city, county, state, country, landmark, address, intersection")
    feature_class = Column(String(1), 
                          comment="P=Populated place, A=Administrative, L=Landmark")
    feature_code = Column(String(10),
                         comment="PPL (Populated Place), ADM1 (First-order admin)")
    
    # Population and importance (optional)
    population = Column(Numeric(12, 0),
                       comment="Population for places, optional")
    importance = Column(Numeric(3, 2), default=0.5,
                       comment="0.0-1.0 based on population/capital status")
    
    # Data quality and confidence
    confidence_score = Column(Numeric(3, 2), default=0.8,
                             comment="0.0-1.0 based on source reliability")
    source_system = Column(String(50), default="geonames",
                          comment="geonames, openstreetmap, user_input, manual")
    source_data = Column(JSONB,
                       comment="Original source location data for reference")
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(),
                       comment="When this location was created")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), 
                       onupdate=func.now(),
                       comment="Last update timestamp")
    is_active = Column(Boolean, default=True,
                      comment="Soft-delete flag")
    
    # Spatial indexing hint for PostGIS
    __table_args__ = (
        Index('idx_location_coordinates', 'latitude', 'longitude'),
        Index('idx_location_country', 'country_code'),
        Index('idx_location_admin1', 'admin1_code'),
        Index('idx_location_type', 'location_type'),
        Index('idx_location_confidence', 'confidence_score'),
        Index('idx_location_active', 'is_active'),
    )

    def __repr__(self):
        return f"<Location(location_id='{self.location_id}', name='{self.display_name}')>"

    @property
    def coordinates(self) -> tuple:
        """Return coordinates as (lat, lng) tuple."""
        return (float(self.latitude), float(self.longitude))

    @property
    def full_address(self) -> str:
        """Return complete hierarchical address."""
        parts = []
        if self.locality:
            parts.append(self.locality)
        if self.admin2_name and self.admin2_name != self.locality:
            parts.append(self.admin2_name)
        if self.admin1_name:
            parts.append(self.admin1_name)
        if self.country_name:
            parts.append(self.country_name)
        return ", ".join(parts)

    def distance_to(self, other_lat: float, other_lng: float) -> float:
        """Calculate distance to another point in kilometers using Haversine formula."""
        return self._haversine_distance(
            float(self.latitude), float(self.longitude),
            other_lat, other_lng
        )

    @staticmethod
    def _haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate great-circle distance between two points on Earth."""
        # Convert decimal degrees to radians
        lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth's radius in kilometers
        r = 6371
        return c * r

    def to_public_dict(self) -> Dict[str, Any]:
        """Return safe public representation."""
        return {
            "location_id": self.location_id,
            "display_name": self.display_name,
            "canonical_name": self.canonical_name,
            "latitude": float(self.latitude),
            "longitude": float(self.longitude),
            "coordinate_precision": self.coordinate_precision,
            "country_code": self.country_code,
            "country_name": self.country_name,
            "admin1_name": self.admin1_name,
            "locality": self.locality,
            "location_type": self.location_type,
            "confidence_score": float(self.confidence_score)
        }

    def to_admin_dict(self) -> Dict[str, Any]:
        """Return full representation for admin use."""
        return {
            "location_id": self.location_id,
            "display_name": self.display_name,
            "canonical_name": self.canonical_name,
            "short_name": self.short_name,
            "latitude": float(self.latitude),
            "longitude": float(self.longitude),
            "coordinate_precision": self.coordinate_precision,
            "country_code": self.country_code,
            "country_name": self.country_name,
            "admin1_code": self.admin1_code,
            "admin1_name": self.admin1_name,
            "admin2_code": self.admin2_code,
            "admin2_name": self.admin2_name,
            "locality": self.locality,
            "location_type": self.location_type,
            "feature_class": self.feature_class,
            "feature_code": self.feature_code,
            "population": int(self.population) if self.population else None,
            "importance": float(self.importance),
            "confidence_score": float(self.confidence_score),
            "source_system": self.source_system,
            "source_data": self.source_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_active": self.is_active
        }


class PersonLocation(Base):
    """
    Link table connecting Persons to Locations with event context.
    
    This enables one person to have multiple location events (last seen, reported,
    found, sightings) with temporal and contextual information.
    """
    __tablename__ = "person_location"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Foreign keys
    pfif_id = Column(String(255), nullable=False, index=True,
                     comment="Reference to person.pfif_id")
    location_id = Column(String(100), nullable=False, index=True,
                        comment="Reference to location.location_id")
    
    # Event context
    event_type = Column(String(50), nullable=False,
                        comment="last_seen, reported_missing, found, sighting, recovery")
    event_date = Column(DateTime(timezone=True),
                       comment="When this location event occurred")
    event_description = Column(Text,
                             comment="Free text description of the event")
    
    # Location relationship details
    relationship_type = Column(String(50), default="primary",
                              comment="primary, secondary, approximate, estimated")
    proximity_description = Column(String(200),
                                  comment="near, north_of, downtown, rural area")
    
    # Source and verification
    source_url = Column(String(500),
                       comment="Original source of this location information")
    source_confidence = Column(String(20), default="medium",
                              comment="high, medium, low - based on source reliability")
    is_verified = Column(Boolean, default=False,
                         comment="True = verified by moderator/expert")
    
    # Privacy and access controls
    is_public = Column(Boolean, default=True,
                      comment="False = law enforcement only")
    precision_fuzzed = Column(Boolean, default=False,
                             comment="True = coordinates fuzzed for privacy")
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(),
                       comment="When this relationship was created")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), 
                       onupdate=func.now(),
                       comment="Last update timestamp")
    created_by = Column(String(100),
                       comment="User/system that created this record")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_person_location_pfif', 'pfif_id'),
        Index('idx_person_location_location', 'location_id'),
        Index('idx_person_location_event', 'event_type'),
        Index('idx_person_location_date', 'event_date'),
        Index('idx_person_location_verified', 'is_verified'),
        Index('idx_person_location_public', 'is_public'),
    )

    def __repr__(self):
        return f"<PersonLocation(pfif_id='{self.pfif_id}', location_id='{self.location_id}', event='{self.event_type}')>"

    @property
    def display_event(self) -> str:
        """Return human-readable event description."""
        event_labels = {
            "last_seen": "Last Seen",
            "reported_missing": "Reported Missing", 
            "found": "Found",
            "sighting": "Sighting",
            "recovery": "Recovery"
        }
        return event_labels.get(self.event_type, self.event_type.replace("_", " ").title())

    def to_dict(self, location: Optional[Location] = None) -> Dict[str, Any]:
        """Return representation with optional location data."""
        result = {
            "id": str(self.id),
            "pfif_id": self.pfif_id,
            "location_id": self.location_id,
            "event_type": self.event_type,
            "display_event": self.display_event,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "event_description": self.event_description,
            "relationship_type": self.relationship_type,
            "proximity_description": self.proximity_description,
            "source_confidence": self.source_confidence,
            "is_verified": self.is_verified,
            "is_public": self.is_public,
            "precision_fuzzed": self.precision_fuzzed,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
        
        if location:
            result["location"] = location.to_public_dict()
        
        return result
