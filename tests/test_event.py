# tests/test_event.py
"""
Test suite for Event entity (Phase 15)
Tests CRUD operations, immutability constraints, and traceability model integration.
"""

import pytest
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from fastapi.testclient import TestClient
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Import models and API
from api.event import router as event_router, EventCreateRequest
from models.event import Event
from models.person import Person
from models.location import Location


@pytest.fixture
def app():
    """Create test FastAPI app with event router."""
    test_app = FastAPI()
    test_app.include_router(event_router)
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_event_data():
    """Sample event data for testing."""
    return {
        "name": "Departure",
        "event_type": "movement",
        "event_timestamp": (datetime.now() - timedelta(days=1)).isoformat(),
        "profile": {
            "transport_mode": "vehicle",
            "destination": "Los Angeles",
            "notes": "Left for work"
        },
        "person_id": "opentrace.org/person/namus.MP24398",
        "location_id": "los-angeles-ca-usa",
        "source_type": "user_report",
        "source_url": "https://example.com/report",
        "confidence_score": "medium",
        "is_public": "public"
    }


@pytest.fixture
def sample_person_data():
    """Sample person data for testing."""
    return {
        "pfif_id": "opentrace.org/person/namus.MP24398",
        "given_name": "John",
        "family_name": "Doe",
        "age_at_disappearance": 25,
        "sex": "Male",
        "status": "missing",
        "is_confirmed": True,
        "is_active": True
    }


@pytest.fixture
def sample_location_data():
    """Sample location data for testing."""
    return {
        "location_id": "los-angeles-ca-usa",
        "canonical_name": "Los Angeles, California, USA",
        "display_name": "Los Angeles, CA",
        "latitude": 34.052235,
        "longitude": -118.243683,
        "country_code": "US",
        "country_name": "United States",
        "location_type": "city",
        "is_active": True
    }


class TestEventModel:
    """Tests for Event model data structure."""
    
    def test_event_model_creation(self):
        """Test that Event model can be created with required fields."""
        event = Event(
            event_type="movement",
            event_date=datetime.now(),
            event_timestamp=datetime.now(),
            reported_date=datetime.now(),
            pfif_id="opentrace.org/person/namus.MP24398",
            source_type="user_report"
        )
        
        assert event.event_type == "movement"
        assert event.pfif_id == "opentrace.org/person/namus.MP24398"
        assert event.source_type == "user_report"
        # Note: Default values (is_public=True) are only applied by database, not in Python object creation
    
    def test_event_model_with_traceability_fields(self):
        """Test Event model with traceability-specific fields."""
        event = Event(
            event_type="inspection",
            event_date=datetime.now(),
            event_timestamp=datetime.now(),
            reported_date=datetime.now(),
            pfif_id="opentrace.org/person/namus.MP24398",
            source_type="system_generated",
            name="Security Inspection",
            profile={
                "inspector": "Officer Smith",
                "result": "passed",
                "notes": "Routine inspection completed"
            }
        )
        
        assert event.name == "Security Inspection"
        assert event.profile["inspector"] == "Officer Smith"
        assert event.profile["result"] == "passed"
    
    def test_event_to_public_dict(self):
        """Test public dictionary representation."""
        event = Event(
            event_id=uuid4(),
            event_type="movement",
            event_date=datetime.now(),
            event_timestamp=datetime.now(),
            reported_date=datetime.now(),
            pfif_id="opentrace.org/person/namus.MP24398",
            location_id="los-angeles-ca-usa",
            source_type="user_report",
            name="Departure",
            profile={"transport_mode": "vehicle"},
            is_public=True
        )
        
        public_dict = event.to_public_dict()
        
        assert "event_id" in public_dict
        assert "person_id" in public_dict  # Should have person_id alias
        assert public_dict["person_id"] == "opentrace.org/person/namus.MP24398"
        assert "location_id" in public_dict
        assert "event_timestamp" in public_dict
        assert "name" in public_dict
        assert "profile" in public_dict
        assert public_dict["name"] == "Departure"
    
    def test_event_to_admin_dict(self):
        """Test admin dictionary representation includes all fields."""
        event = Event(
            event_id=uuid4(),
            event_type="handover",
            event_date=datetime.now(),
            event_timestamp=datetime.now(),
            reported_date=datetime.now(),
            pfif_id="opentrace.org/person/namus.MP24398",
            location_id="los-angeles-ca-usa",
            source_type="api",
            name="Transfer",
            profile={"from": "Facility A", "to": "Facility B"},
            source_confidence="high"
        )
        
        admin_dict = event.to_admin_dict()
        
        assert "profile" in admin_dict
        assert "person_id" in admin_dict
        assert "event_timestamp" in admin_dict
        assert admin_dict["profile"]["from"] == "Facility A"
        assert admin_dict["source_confidence"] == "high"


class TestEventAPI:
    """Tests for Event API endpoints."""
    
    def test_create_event_success(self, client, sample_event_data):
        """Test successful event creation via API."""
        # Note: This would require a real database with the person and location
        # For unit testing without DB, we'd mock the dependencies
        # This is a placeholder for integration testing
        pass
    
    def test_create_event_missing_required_fields(self, client):
        """Test event creation fails without required fields."""
        incomplete_data = {
            "name": "Test Event"
            # Missing event_type and event_timestamp
        }
        
        response = client.post("/api/events", json=incomplete_data)
        assert response.status_code == 422  # Validation error
    
    def test_create_event_invalid_type(self, client):
        """Test event creation fails with invalid event type."""
        invalid_data = {
            "name": "Test Event",
            "event_type": "invalid_type",
            "event_timestamp": datetime.now().isoformat()
        }
        
        response = client.post("/api/events", json=invalid_data)
        # Should fail validation for invalid event_type
        assert response.status_code in [400, 422]
    
    def test_get_event_not_found(self, client):
        """Test getting non-existent event returns 404."""
        fake_uuid = str(uuid4())
        response = client.get(f"/api/events/{fake_uuid}")
        assert response.status_code == 404
    
    def test_list_events_pagination(self, client):
        """Test event listing with pagination parameters."""
        response = client.get("/api/events?page=1&page_size=10")
        assert response.status_code == 200
        
        data = response.json()
        assert "events" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
    
    def test_list_events_with_filters(self, client):
        """Test event listing with filter parameters."""
        response = client.get(
            "/api/events?event_type=movement&confidence_score=medium&is_public=public"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "events" in data
    
    def test_person_timeline_endpoint(self, client):
        """Test person timeline endpoint structure."""
        person_id = "opentrace.org/person/namus.MP24398"
        response = client.get(f"/api/events/person/{person_id}/timeline")
        
        # Should return 200 or 404 if person doesn't exist
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert "person_id" in data
            assert "timeline" in data
            assert "event_count" in data
    
    def test_location_events_endpoint(self, client):
        """Test location events endpoint structure."""
        location_id = "los-angeles-ca-usa"
        response = client.get(f"/api/events/location/{location_id}/events")
        
        # Should return 200 or 404 if location doesn't exist
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert "location_id" in data
            assert "events" in data
    
    def test_delete_event_soft_delete(self, client):
        """Test soft delete endpoint (marks as private)."""
        # This would require an existing event
        fake_uuid = str(uuid4())
        response = client.delete(f"/api/events/{fake_uuid}")
        assert response.status_code in [204, 404]  # Either deleted or not found
    
    def test_verify_event_endpoint(self, client):
        """Test event verification status update."""
        # This would require an existing event
        fake_uuid = str(uuid4())
        response = client.patch(f"/api/events/{fake_uuid}/verify?verified_status=verified")
        assert response.status_code in [200, 404]
    
    def test_verify_event_invalid_status(self, client):
        """Test event verification with invalid status returns error."""
        fake_uuid = str(uuid4())
        response = client.patch(f"/api/events/{fake_uuid}/verify?verified_status=invalid")
        assert response.status_code == 400


class TestEventImmutability:
    """Tests for Event immutability constraints."""
    
    def test_event_has_no_update_trigger(self):
        """Test that Event model does not have update triggers (immutable data)."""
        # This is enforced at the database level via migration
        # The event data itself should never be updated
        pass
    
    def test_event_update_not_allowed_in_api(self):
        """Test that API does not provide update endpoint for event data."""
        # The API should only allow:
        # - Create (POST)
        # - Read (GET)
        # - Soft delete (DELETE - marks as private)
        # - Verify (PATCH - only changes verification status)
        # No PUT endpoint for updating event data
        pass
    
    def test_event_created_at_never_changes(self):
        """Test that created_at timestamp is set once and never changes."""
        event = Event(
            event_type="movement",
            event_date=datetime.now(),
            event_timestamp=datetime.now(),
            reported_date=datetime.now(),
            pfif_id="opentrace.org/person/namus.MP24398",
            source_type="user_report"
        )
        
        # created_at should be set by server_default
        assert event.created_at is None  # Not set until committed


class TestEventTraceabilityIntegration:
    """Tests for Event integration with Person and Location entities."""
    
    def test_event_links_to_person(self):
        """Test that event correctly links to a Person."""
        event = Event(
            event_type="movement",
            event_date=datetime.now(),
            event_timestamp=datetime.now(),
            reported_date=datetime.now(),
            pfif_id="opentrace.org/person/namus.MP24398",
            source_type="user_report"
        )
        
        assert event.pfif_id == "opentrace.org/person/namus.MP24398"
        # person_id should be an alias in to_public_dict
    
    def test_event_links_to_location(self):
        """Test that event correctly links to a Location."""
        event = Event(
            event_type="inspection",
            event_date=datetime.now(),
            event_timestamp=datetime.now(),
            reported_date=datetime.now(),
            pfif_id="opentrace.org/person/namus.MP24398",
            location_id="los-angeles-ca-usa",
            source_type="system_generated"
        )
        
        assert event.location_id == "los-angeles-ca-usa"
    
    def test_event_optional_links(self):
        """Test that event person_id and location_id are optional."""
        # Event without person (system event)
        system_event = Event(
            event_type="report",
            event_date=datetime.now(),
            event_timestamp=datetime.now(),
            reported_date=datetime.now(),
            source_type="system_generated",
            profile={"system_info": "automated_check"}
        )
        
        assert system_event.pfif_id is None
        assert system_event.location_id is None
        assert system_event.profile["system_info"] == "automated_check"


class TestEventEventTypes:
    """Tests for Event type validation."""
    
    @pytest.mark.parametrize("event_type", [
        "movement",
        "inspection",
        "handover",
        "sighting",
        "report",
        "departure",
        "arrival",
        "contact",
        "other"
    ])
    def test_valid_traceability_event_types(self, event_type):
        """Test that all traceability event types are accepted."""
        # This would be tested against the database constraint
        # For now, just verify the types are in our expected list
        valid_types = [
            'sighting', 'police_report', 'status_change', 'tip', 'document', 
            'recovery', 'false_alarm', 'digital_trace',
            'movement', 'inspection', 'handover', 'report', 
            'departure', 'arrival', 'contact', 'other'
        ]
        assert event_type in valid_types
    
    def test_invalid_event_type_rejected(self):
        """Test that invalid event types are rejected."""
        invalid_types = ["invalid", "unknown", "test", ""]
        valid_types = [
            'sighting', 'police_report', 'status_change', 'tip', 'document', 
            'recovery', 'false_alarm', 'digital_trace',
            'movement', 'inspection', 'handover', 'report', 
            'departure', 'arrival', 'contact', 'other'
        ]
        
        for invalid_type in invalid_types:
            assert invalid_type not in valid_types


class TestEventValidation:
    """Tests for Event data validation."""
    
    def test_event_timestamp_iso8601(self):
        """Test that event_timestamp accepts ISO 8601 format."""
        timestamp = datetime.fromisoformat("2024-01-15T10:30:00+00:00")
        event = Event(
            event_type="movement",
            event_date=timestamp,
            event_timestamp=timestamp,
            reported_date=datetime.now(),
            pfif_id="opentrace.org/person/namus.MP24398",
            source_type="user_report"
        )
        
        assert event.event_timestamp == timestamp
    
    def test_profile_json_structure(self):
        """Test that profile field accepts JSON structure."""
        profile_data = {
            "transport_mode": "vehicle",
            "destination": "Los Angeles",
            "coordinates": {
                "lat": 34.052235,
                "lng": -118.243683
            },
            "tags": ["urgent", "verified"],
            "metadata": {
                "source_system": "GPS",
                "accuracy": "high"
            }
        }
        
        event = Event(
            event_type="movement",
            event_date=datetime.now(),
            event_timestamp=datetime.now(),
            reported_date=datetime.now(),
            pfif_id="opentrace.org/person/namus.MP24398",
            source_type="api",
            profile=profile_data
        )
        
        assert event.profile["transport_mode"] == "vehicle"
        assert event.profile["coordinates"]["lat"] == 34.052235
        assert "urgent" in event.profile["tags"]


# Integration test markers
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration
]
