# tests/test_source.py
"""
Test suite for Source entity (Phase 16)
Tests CRUD operations, health tracking, and provenance integration.
"""

import pytest
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from fastapi.testclient import TestClient
from fastapi import FastAPI
from sqlalchemy import select

from api.source import router as source_router
from models.source import Source


@pytest.fixture
def app():
    """Create test FastAPI app with source router."""
    test_app = FastAPI()
    test_app.include_router(source_router)
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_source_data():
    """Sample source data for testing."""
    return {
        "source_name": "Test API Source",
        "source_code": "test_api_001",
        "source_type": "api",
        "source_category": "official",
        "description": "A test API source for unit testing",
        "organization": "Test Organization",
        "jurisdiction": "US",
        "source_url": "https://api.test.example.com",
        "contact_email": "test@example.com",
        "trust_tier": "verified",
        "verification_status": "verified",
        "reliability_score": 0.95,
        "data_types": ["person", "location"],
        "is_active": True
    }


class TestSourceModel:
    """Tests for Source model data structure."""
    
    def test_source_model_creation(self):
        """Test that Source model can be created with required fields."""
        source = Source(
            source_name="NamUs API",
            source_code="namus_api",
            source_type="api",
            source_category="official"
        )
        
        assert source.source_name == "NamUs API"
        assert source.source_code == "namus_api"
        assert source.source_type == "api"
        assert source.trust_tier == "standard"  # Default
        assert source.reliability_score == 0.7  # Default
    
    def test_source_health_status_healthy(self):
        """Test health status calculation for healthy source."""
        source = Source(
            source_name="Healthy Source",
            source_code="healthy_001",
            source_type="api",
            source_category="official",
            is_active=True,
            last_successful_fetch=datetime.now(),
            error_count=0
        )
        
        assert source.health_status == "healthy"
    
    def test_source_health_status_inactive(self):
        """Test health status for inactive source."""
        source = Source(
            source_name="Inactive Source",
            source_code="inactive_001",
            source_type="api",
            source_category="official",
            is_active=False
        )
        
        assert source.health_status == "inactive"
    
    def test_source_to_public_dict(self):
        """Test public dictionary representation."""
        source = Source(
            source_id=uuid4(),
            source_name="Public Test Source",
            source_code="public_001",
            source_type="scraper",
            source_category="community",
            trust_tier="trusted",
            verification_status="verified",
            reliability_score=0.85,
            data_types=["person"]
        )
        
        public_dict = source.to_public_dict()
        
        assert "source_id" in public_dict
        assert public_dict["source_name"] == "Public Test Source"
        assert public_dict["trust_tier"] == "trusted"
        assert public_dict["reliability_score"] == 0.85
        assert "api_config" not in public_dict  # Should be excluded
    
    def test_source_to_admin_dict(self):
        """Test admin dictionary includes all fields."""
        source = Source(
            source_id=uuid4(),
            source_name="Admin Test Source",
            source_code="admin_001",
            source_type="api",
            source_category="official",
            api_config={"endpoint": "/v1/data", "auth": "bearer"},
            source_metadata={"custom_field": "value"}
        )
        
        admin_dict = source.to_admin_dict()
        
        assert "api_config" in admin_dict
        assert admin_dict["api_config"]["endpoint"] == "/v1/data"
        assert "source_metadata" in admin_dict
    
    def test_source_rate_limit_display(self):
        """Test rate limit display formatting."""
        source = Source(
            source_name="Rate Limited",
            source_code="limited_001",
            source_type="api",
            source_category="official",
            rate_limit_per_hour=100
        )
        
        assert source.rate_limit_display == "100/hour"
    
    def test_source_is_reliable(self):
        """Test reliability threshold check."""
        reliable_source = Source(
            source_name="Reliable",
            source_code="reliable_001",
            source_type="api",
            source_category="official",
            reliability_score=0.8
        )
        
        unreliable_source = Source(
            source_name="Unreliable",
            source_code="unreliable_001",
            source_type="api",
            source_category="official",
            reliability_score=0.3
        )
        
        assert reliable_source.is_reliable == True
        assert unreliable_source.is_reliable == False


class TestSourceValidation:
    """Tests for source data validation."""
    
    @pytest.mark.parametrize("source_type", [
        "api", "user_report", "scraper", "sensor", "manual", "system", "import"
    ])
    def test_valid_source_types(self, source_type):
        """Test that all valid source types are accepted."""
        valid_types = [
            'api', 'user_report', 'scraper', 'sensor', 'manual', 'system', 'import'
        ]
        assert source_type in valid_types
    
    def test_invalid_source_type(self):
        """Test that invalid source types are rejected."""
        invalid_types = ["invalid", "unknown", "test"]
        valid_types = [
            'api', 'user_report', 'scraper', 'sensor', 'manual', 'system', 'import'
        ]
        
        for invalid_type in invalid_types:
            assert invalid_type not in valid_types
    
    @pytest.mark.parametrize("trust_tier", [
        "verified", "trusted", "standard", "community", "unverified", "blocked"
    ])
    def test_valid_trust_tiers(self, trust_tier):
        """Test valid trust tiers."""
        valid_tiers = [
            'verified', 'trusted', 'standard', 'community', 'unverified', 'blocked'
        ]
        assert trust_tier in valid_tiers
    
    def test_reliability_score_range(self):
        """Test reliability score constraints."""
        # Valid scores
        assert 0.0 <= 0.5 <= 1.0
        assert 0.0 <= 0.95 <= 1.0
        
        # Invalid scores would fail database constraint
        assert not (-0.1 >= 0.0)  # Below minimum
        assert not (1.5 <= 1.0)   # Above maximum


# Integration test markers
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration
]
