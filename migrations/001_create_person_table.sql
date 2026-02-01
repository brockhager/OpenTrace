-- Migration: Create Person table (Phase 13)
-- This establishes the unified Person entity as the core identity model
-- Run this after deploying to Railway: psql -f migrations/001_create_person_table.sql

-- Create the canonical Person table
CREATE TABLE person (
    -- Stable public identifier (PFIF-compliant)
    pfif_id VARCHAR(255) PRIMARY KEY,
    
    -- Core identity fields (nullable - some sources only have partial info)
    given_name VARCHAR(255),
    family_name VARCHAR(255),
    alternate_names TEXT[], -- PostgreSQL array for aliases, nicknames
    
    -- Demographics
    age_at_disappearance INTEGER,
    sex VARCHAR(50),
    
    -- Status and timing
    status VARCHAR(50) DEFAULT 'missing' CHECK (status IN ('missing', 'unidentified', 'found')),
    date_last_seen TIMESTAMP WITH TIME ZONE,
    date_reported TIMESTAMP WITH TIME ZONE,
    
    -- Data quality and workflow
    is_confirmed BOOLEAN DEFAULT FALSE,
    source_confidence VARCHAR(20) DEFAULT 'medium' CHECK (source_confidence IN ('high', 'medium', 'low')),
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    entry_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Source tracking (minimal - details in intel_item)
    primary_source VARCHAR(100),
    source_id VARCHAR(255),
    source_url TEXT,
    
    -- Privacy and compliance
    is_active BOOLEAN DEFAULT TRUE,
    data_sensitivity VARCHAR(20) DEFAULT 'standard' CHECK (data_sensitivity IN ('standard', 'sensitive', 'restricted'))
);

-- Create indexes for performance
CREATE INDEX idx_person_pfif_id ON person(pfif_id);
CREATE INDEX idx_person_names ON person(given_name, family_name) WHERE given_name IS NOT NULL AND family_name IS NOT NULL;
CREATE INDEX idx_person_status ON person(status);
CREATE INDEX idx_person_confirmed ON person(is_confirmed);
CREATE INDEX idx_person_source ON person(primary_source);
CREATE INDEX idx_person_active ON person(is_active);
CREATE INDEX idx_person_last_seen ON person(date_last_seen) WHERE date_last_seen IS NOT NULL;

-- Create trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_person_updated_at 
    BEFORE UPDATE ON person 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE person IS 'Canonical Person entity representing missing, unidentified, or found individuals';
COMMENT ON COLUMN person.pfif_id IS 'Stable public identifier (PFIF-compliant), e.g., opentrace.org/person/namus.MP24398';
COMMENT ON COLUMN person.given_name IS 'First name';
COMMENT ON COLUMN person.family_name IS 'Last name';
COMMENT ON COLUMN person.alternate_names IS 'Array of aliases, nicknames, maiden names';
COMMENT ON COLUMN person.age_at_disappearance IS 'Age when person went missing';
COMMENT ON COLUMN person.sex IS 'Male, Female, Unknown';
COMMENT ON COLUMN person.status IS 'missing, unidentified, found';
COMMENT ON COLUMN person.date_last_seen IS 'Date person was last seen';
COMMENT ON COLUMN person.date_reported IS 'Date case was officially reported';
COMMENT ON COLUMN person.is_confirmed IS 'True = verified by moderator, False = pending review';
COMMENT ON COLUMN person.source_confidence IS 'high, medium, low - based on source reliability';
COMMENT ON COLUMN person.primary_source IS 'Primary data source: namus, interpol, charley, pdf, etc.';
COMMENT ON COLUMN person.source_id IS 'Original ID from source system';
COMMENT ON COLUMN person.source_url IS 'Link to original source record';
COMMENT ON COLUMN person.is_active IS 'Soft-delete flag for GDPR compliance';
COMMENT ON COLUMN person.data_sensitivity IS 'standard, sensitive, restricted - affects access controls';

-- Grant permissions (adjust as needed for your deployment)
-- GRANT SELECT, INSERT, UPDATE ON person TO opentrace_app;
-- GRANT USAGE, SELECT ON SEQUENCE person_pfif_id_seq TO opentrace_app;
