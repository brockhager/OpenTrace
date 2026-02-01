-- Migration: Create Location tables (Phase 14)
-- This establishes the canonical Location entity and Person-Location relationships
-- Run this after Phase 13 deployment: psql -f migrations/002_create_location_tables.sql

-- Enable PostGIS extension for spatial indexing (conditionally)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name='postgis') THEN
    EXECUTE 'CREATE EXTENSION IF NOT EXISTS postgis';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name='postgis_topology') THEN
    EXECUTE 'CREATE EXTENSION IF NOT EXISTS postgis_topology';
  END IF;
END;
$$;

-- Create the canonical Location table
CREATE TABLE location (
    -- Stable identifier
    location_id VARCHAR(100) PRIMARY KEY,
    
    -- Canonical place names
    canonical_name VARCHAR(500) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    short_name VARCHAR(100),
    
    -- Geographic coordinates (WGS84)
    latitude NUMERIC(10, 8) NOT NULL,
    longitude NUMERIC(11, 8) NOT NULL,
    coordinate_precision VARCHAR(20) DEFAULT 'approximate',
    
    -- Administrative hierarchy (ISO standards where possible)
    country_code VARCHAR(2) NOT NULL,
    country_name VARCHAR(100) NOT NULL,
    admin1_code VARCHAR(10),
    admin1_name VARCHAR(100),
    admin2_code VARCHAR(20),
    admin2_name VARCHAR(100),
    locality VARCHAR(100),
    
    -- Location classification
    location_type VARCHAR(50) NOT NULL,
    feature_class VARCHAR(1),
    feature_code VARCHAR(10),
    
    -- Population and importance (optional)
    population NUMERIC(12, 0),
    importance NUMERIC(3, 2) DEFAULT 0.5,
    
    -- Data quality and confidence
    confidence_score NUMERIC(3, 2) DEFAULT 0.8,
    source_system VARCHAR(50) DEFAULT 'geonames',
    source_data JSONB,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- Create Person-Location link table
CREATE TABLE person_location (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign keys
    pfif_id VARCHAR(255) NOT NULL,
    location_id VARCHAR(100) NOT NULL,
    
    -- Event context
    event_type VARCHAR(50) NOT NULL,
    event_date TIMESTAMP WITH TIME ZONE,
    event_description TEXT,
    
    -- Location relationship details
    relationship_type VARCHAR(50) DEFAULT 'primary',
    proximity_description VARCHAR(200),
    
    -- Source and verification
    source_url VARCHAR(500),
    source_confidence VARCHAR(20) DEFAULT 'medium',
    is_verified BOOLEAN DEFAULT FALSE,
    
    -- Privacy and access controls
    is_public BOOLEAN DEFAULT TRUE,
    precision_fuzzed BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100)
);

-- Create indexes for Location table
CREATE INDEX idx_location_coordinates ON location(latitude, longitude);
CREATE INDEX idx_location_country ON location(country_code);
CREATE INDEX idx_location_admin1 ON location(admin1_code);
CREATE INDEX idx_location_type ON location(location_type);
CREATE INDEX idx_location_confidence ON location(confidence_score);
CREATE INDEX idx_location_active ON location(is_active);

-- Create spatial index for geographic queries (only if PostGIS is installed)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname='postgis') THEN
    EXECUTE $$
      CREATE INDEX idx_location_spatial ON location USING GIST (
        ST_SetSRID(ST_MakePoint(longitude::double precision, latitude::double precision), 4326)
      );
    $$;
  END IF;
END;
$$;

-- Create indexes for PersonLocation table
CREATE INDEX idx_person_location_pfif ON person_location(pfif_id);
CREATE INDEX idx_person_location_location ON person_location(location_id);
CREATE INDEX idx_person_location_event ON person_location(event_type);
CREATE INDEX idx_person_location_date ON person_location(event_date);
CREATE INDEX idx_person_location_verified ON person_location(is_verified);
CREATE INDEX idx_person_location_public ON person_location(is_public);

-- Create composite index for common queries
CREATE INDEX idx_person_location_composite ON person_location(pfif_id, event_type, is_public);

-- Add foreign key constraints
ALTER TABLE person_location 
ADD CONSTRAINT fk_person_location_person 
FOREIGN KEY (pfif_id) REFERENCES person(pfif_id) ON DELETE CASCADE;

ALTER TABLE person_location 
ADD CONSTRAINT fk_person_location_location 
FOREIGN KEY (location_id) REFERENCES location(location_id) ON DELETE RESTRICT;

-- Add check constraints
ALTER TABLE location 
ADD CONSTRAINT chk_coordinate_precision 
CHECK (coordinate_precision IN ('exact', 'approximate', 'region', 'country'));

ALTER TABLE location 
ADD CONSTRAINT chk_confidence_score 
CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0);

ALTER TABLE location 
ADD CONSTRAINT chk_importance 
CHECK (importance >= 0.0 AND importance <= 1.0);

ALTER TABLE person_location 
ADD CONSTRAINT chk_event_type 
CHECK (event_type IN ('last_seen', 'reported_missing', 'found', 'sighting', 'recovery', 'other'));

ALTER TABLE person_location 
ADD CONSTRAINT chk_relationship_type 
CHECK (relationship_type IN ('primary', 'secondary', 'approximate', 'estimated'));

ALTER TABLE person_location 
ADD CONSTRAINT chk_source_confidence 
CHECK (source_confidence IN ('high', 'medium', 'low'));

-- Create trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_location_updated_at 
    BEFORE UPDATE ON location 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_person_location_updated_at 
    BEFORE UPDATE ON person_location 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE location IS 'Canonical Location entity representing standardized geographic places';
COMMENT ON COLUMN location.location_id IS 'Canonical ID: los-angeles-ca-usa, paris-75-fr';
COMMENT ON COLUMN location.canonical_name IS 'Los Angeles, California, USA';
COMMENT ON COLUMN location.display_name IS 'Los Angeles, CA';
COMMENT ON COLUMN location.coordinate_precision IS 'exact, approximate, region, country';
COMMENT ON COLUMN location.confidence_score IS '0.0-1.0 based on source reliability';
COMMENT ON COLUMN location.source_data IS 'Original source location data for reference';

COMMENT ON TABLE person_location IS 'Link table connecting Persons to Locations with event context';
COMMENT ON COLUMN person_location.event_type IS 'last_seen, reported_missing, found, sighting, recovery';
COMMENT ON COLUMN person_location.relationship_type IS 'primary, secondary, approximate, estimated';
COMMENT ON COLUMN person_location.is_public IS 'False = law enforcement only';
COMMENT ON COLUMN person_location.precision_fuzzed IS 'True = coordinates fuzzed for privacy';

-- Grant permissions (adjust as needed for your deployment)
-- GRANT SELECT, INSERT, UPDATE ON location TO opentrace_app;
-- GRANT SELECT, INSERT, UPDATE ON person_location TO opentrace_app;
-- GRANT USAGE ON SCHEMA public TO opentrace_app;
