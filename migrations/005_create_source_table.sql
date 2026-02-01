-- Migration: Create Source table (Phase 16)
-- This establishes the canonical Source entity for provenance and data lineage
-- Run this after Phase 15 deployment: psql -f migrations/005_create_source_table.sql

-- Create the Source table
CREATE TABLE source (
    -- Stable identifier
    source_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Source identification
    source_name VARCHAR(255) NOT NULL UNIQUE,
    source_code VARCHAR(50) NOT NULL UNIQUE,
    
    -- Source classification
    source_type VARCHAR(50) NOT NULL,
    source_category VARCHAR(50) NOT NULL,
    
    -- Source metadata
    description TEXT,
    organization VARCHAR(255),
    jurisdiction VARCHAR(100),
    
    -- Contact and URL information
    source_url VARCHAR(1000),
    contact_email VARCHAR(255),
    documentation_url VARCHAR(1000),
    
    -- Reliability and trust scoring
    reliability_score NUMERIC(3, 2) DEFAULT 0.7,
    trust_tier VARCHAR(20) DEFAULT 'standard',
    verification_status VARCHAR(20) DEFAULT 'unverified',
    
    -- Source capabilities and metadata
    data_types JSONB,
    api_config JSONB,
    source_metadata JSONB,
    
    -- Operational status
    is_active BOOLEAN DEFAULT TRUE,
    last_successful_fetch TIMESTAMP WITH TIME ZONE,
    last_failed_fetch TIMESTAMP WITH TIME ZONE,
    error_count INTEGER DEFAULT 0,
    
    -- Rate limiting and quotas
    rate_limit_per_hour INTEGER,
    rate_limit_per_day INTEGER,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Audit
    created_by VARCHAR(100)
);

-- Create indexes for Source table
CREATE INDEX idx_source_code ON source(source_code);
CREATE INDEX idx_source_type ON source(source_type);
CREATE INDEX idx_source_category ON source(source_category);
CREATE INDEX idx_source_active ON source(is_active);
CREATE INDEX idx_source_trust ON source(trust_tier);
CREATE INDEX idx_source_verification ON source(verification_status);
CREATE INDEX idx_source_reliability ON source(reliability_score);
CREATE INDEX idx_source_data_types ON source USING GIN(data_types);

-- Add check constraints
ALTER TABLE source 
ADD CONSTRAINT chk_source_type 
CHECK (source_type IN ('api', 'user_report', 'scraper', 'sensor', 'manual', 'system', 'import'));

ALTER TABLE source 
ADD CONSTRAINT chk_source_category 
CHECK (source_category IN ('official', 'community', 'automated', 'verified', 'unverified', 'sandbox'));

ALTER TABLE source 
ADD CONSTRAINT chk_trust_tier 
CHECK (trust_tier IN ('verified', 'trusted', 'standard', 'community', 'unverified', 'blocked'));

ALTER TABLE source 
ADD CONSTRAINT chk_verification_status 
CHECK (verification_status IN ('verified', 'pending', 'unverified', 'suspended', 'deprecated', 'revoked'));

ALTER TABLE source 
ADD CONSTRAINT chk_reliability_score 
CHECK (reliability_score >= 0.0 AND reliability_score <= 1.0);

-- Create trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_source_updated_at 
    BEFORE UPDATE ON source 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE source IS 'Canonical Source entity representing data provenance and lineage';
COMMENT ON COLUMN source.source_id IS 'Globally unique identifier for this source';
COMMENT ON COLUMN source.source_name IS 'Human-readable name: NamUs API, User Report Portal';
COMMENT ON COLUMN source.source_code IS 'Short code: namus, user_portal, sensor_001';
COMMENT ON COLUMN source.source_type IS 'api, user_report, scraper, sensor, manual, system, import';
COMMENT ON COLUMN source.source_category IS 'official, community, automated, verified, unverified, sandbox';
COMMENT ON COLUMN source.reliability_score IS '0.0-1.0 automated reliability score based on history';
COMMENT ON COLUMN source.trust_tier IS 'verified, trusted, standard, community, unverified, blocked';
COMMENT ON COLUMN source.data_types IS 'JSON array of data types provided: person, location, event, intel';
COMMENT ON COLUMN source.api_config IS 'API configuration for api type sources';
COMMENT ON COLUMN source.source_metadata IS 'Flexible metadata for source-specific attributes';

-- Insert default sources (based on current /sources endpoint)
INSERT INTO source (source_name, source_code, source_type, source_category, description, organization, trust_tier, verification_status, data_types, is_active) VALUES
('NamUs', 'namus', 'scraper', 'official', 'National Missing and Unidentified Persons System', 'US Department of Justice', 'verified', 'verified', '["person", "location"]', true),
('Interpol Yellow Notices', 'interpol', 'api', 'official', 'International missing persons database', 'Interpol', 'verified', 'verified', '["person"]', true),
('The Charley Project', 'charley', 'scraper', 'community', 'Community-driven missing persons database', 'Charley Project', 'trusted', 'verified', '["person"]', true),
('User Report Portal', 'user_portal', 'user_report', 'community', 'Direct user submissions and reports', 'Open Trace Community', 'standard', 'verified', '["person", "location", "event", "intel"]', true),
('System Generated', 'system', 'system', 'automated', 'Automated system events and processing', 'Open Trace', 'verified', 'verified', '["event"]', true);

-- Grant permissions (adjust as needed for your deployment)
-- GRANT SELECT, INSERT, UPDATE ON source TO opentrace_app;
-- GRANT USAGE ON SCHEMA public TO opentrace_app;
