-- Migration: Create Event tables (Phase 15)
-- This establishes the Event entity for temporal interactions and EventEvidence for attachments
-- Run this after Phase 14 deployment: psql -f migrations/004_create_event_tables.sql

-- Create the Event table
CREATE TABLE event (
    -- Stable identifier
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Entity relationships (traceability model: person_id and location_id are optional)
    pfif_id VARCHAR(255) NOT NULL,
    person_id VARCHAR(255),  -- Alias for pfif_id for traceability model consistency
    location_id VARCHAR(100),
    
    -- Event classification
    event_type VARCHAR(50) NOT NULL,
    event_subtype VARCHAR(50),
    
    -- Temporal data (traceability model)
    event_date TIMESTAMP WITH TIME ZONE NOT NULL,
    event_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),  -- ISO 8601 timestamp for traceability
    reported_date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Event content (traceability model: name and profile fields)
    name VARCHAR(500),  -- Human-readable label for traceability model
    title VARCHAR(500),
    description TEXT,
    summary TEXT,
    profile JSONB,  -- Structured metadata for traceability model
    
    -- Source and verification
    source_type VARCHAR(50) NOT NULL,
    source_url VARCHAR(500),
    source_confidence VARCHAR(20) DEFAULT 'medium',
    is_verified BOOLEAN DEFAULT FALSE,
    
    -- Evidence and attachments
    evidence_count INTEGER DEFAULT 0,
    has_media BOOLEAN DEFAULT FALSE,
    
    -- Geographic context
    location_description VARCHAR(500),
    location_precision VARCHAR(20) DEFAULT 'unknown',
    
    -- People involved
    reporter_name VARCHAR(200),
    reporter_contact VARCHAR(500),
    witness_count INTEGER DEFAULT 0,
    
    -- Status and workflow
    event_status VARCHAR(20) DEFAULT 'active',
    priority VARCHAR(20) DEFAULT 'medium',
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100),
    tags TEXT[], -- PostgreSQL array
    
    -- AI processing
    ai_processed BOOLEAN DEFAULT FALSE,
    ai_confidence NUMERIC(3, 2),
    ai_entities JSONB,
    ai_sentiment VARCHAR(20),
    
    -- Privacy and access
    is_public BOOLEAN DEFAULT TRUE,
    access_level VARCHAR(20) DEFAULT 'public'
);

-- Create the EventEvidence table
CREATE TABLE event_evidence (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Relationship to event
    event_id UUID NOT NULL,
    
    -- Evidence metadata
    evidence_type VARCHAR(50) NOT NULL,
    file_name VARCHAR(500),
    file_size BIGINT,
    mime_type VARCHAR(100),
    file_hash VARCHAR(64),
    
    -- Storage information
    storage_url VARCHAR(1000),
    thumbnail_url VARCHAR(1000),
    preview_url VARCHAR(1000),
    
    -- Content analysis
    description TEXT,
    extracted_text TEXT,
    ai_analysis VARCHAR(1000),
    ai_confidence VARCHAR(20),
    
    -- Media-specific metadata
    width INTEGER,
    height INTEGER,
    duration INTEGER,
    
    -- Verification and processing
    is_verified BOOLEAN DEFAULT FALSE,
    verification_notes TEXT,
    processing_status VARCHAR(20) DEFAULT 'pending',
    
    -- Privacy and access controls
    is_public BOOLEAN DEFAULT FALSE,
    access_level VARCHAR(20) DEFAULT 'restricted',
    contains_pii BOOLEAN DEFAULT FALSE,
    
    -- Source information
    source_type VARCHAR(50),
    source_url VARCHAR(500),
    uploaded_by VARCHAR(100),
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    tags VARCHAR(500)
);

-- Create indexes for Event table
CREATE INDEX idx_event_pfif_id ON event(pfif_id);
CREATE INDEX idx_event_person_id ON event(person_id);  -- For traceability model queries
CREATE INDEX idx_event_location_id ON event(location_id);
CREATE INDEX idx_event_type_date ON event(event_type, event_date);
CREATE INDEX idx_event_timestamp ON event(event_timestamp);  -- For traceability model temporal queries
CREATE INDEX idx_event_status ON event(event_status);
CREATE INDEX idx_event_priority ON event(priority);
CREATE INDEX idx_event_created ON event(created_at);
CREATE INDEX idx_event_verified ON event(is_verified);
CREATE INDEX idx_event_public ON event(is_public);
CREATE INDEX idx_event_source_type ON event(source_type);
CREATE INDEX idx_event_composite ON event(pfif_id, event_date, event_status);
CREATE INDEX idx_event_traceability ON event(person_id, location_id, event_timestamp);  -- For traceability graph queries
CREATE INDEX idx_event_ai_processed ON event(ai_processed);
CREATE INDEX idx_event_tags ON event USING GIN(tags);
CREATE INDEX idx_event_profile ON event USING GIN(profile jsonb_path_ops);  -- For profile JSON queries

-- Create indexes for EventEvidence table
CREATE INDEX idx_evidence_event_id ON event_evidence(event_id);
CREATE INDEX idx_evidence_type ON event_evidence(evidence_type);
CREATE INDEX idx_evidence_file_hash ON event_evidence(file_hash);
CREATE INDEX idx_evidence_verified ON event_evidence(is_verified);
CREATE INDEX idx_evidence_public ON event_evidence(is_public);
CREATE INDEX idx_evidence_processing ON event_evidence(processing_status);
CREATE INDEX idx_evidence_contains_pii ON event_evidence(contains_pii);
CREATE INDEX idx_evidence_created ON event_evidence(created_at);

-- Add foreign key constraints
ALTER TABLE event 
ADD CONSTRAINT fk_event_person 
FOREIGN KEY (pfif_id) REFERENCES person(pfif_id) ON DELETE CASCADE;

ALTER TABLE event 
ADD CONSTRAINT fk_event_location 
FOREIGN KEY (location_id) REFERENCES location(location_id) ON DELETE SET NULL;

ALTER TABLE event_evidence 
ADD CONSTRAINT fk_evidence_event 
FOREIGN KEY (event_id) REFERENCES event(event_id) ON DELETE CASCADE;

-- Add check constraints
ALTER TABLE event 
ADD CONSTRAINT chk_event_type 
CHECK (event_type IN (
    -- Original event types
    'sighting', 'police_report', 'status_change', 'tip', 'document', 'recovery', 'false_alarm', 'digital_trace',
    -- Traceability model types (Phase 15)
    'movement', 'inspection', 'handover', 'report', 'departure', 'arrival', 'contact', 'other'
));

ALTER TABLE event 
ADD CONSTRAINT chk_event_status 
CHECK (event_status IN ('active', 'resolved', 'false_alarm', 'duplicate', 'archived'));

ALTER TABLE event 
ADD CONSTRAINT chk_priority 
CHECK (priority IN ('low', 'medium', 'high', 'critical'));

ALTER TABLE event 
ADD CONSTRAINT chk_source_confidence 
CHECK (source_confidence IN ('high', 'medium', 'low'));

ALTER TABLE event 
ADD CONSTRAINT chk_access_level 
CHECK (access_level IN ('public', 'law_enforcement', 'admin', 'restricted'));

ALTER TABLE event 
ADD CONSTRAINT chk_ai_sentiment 
CHECK (ai_sentiment IN ('positive', 'negative', 'neutral'));

ALTER TABLE event_evidence 
ADD CONSTRAINT chk_evidence_type 
CHECK (evidence_type IN ('photo', 'video', 'audio', 'document', 'screenshot', 'text', 'url'));

ALTER TABLE event_evidence 
ADD CONSTRAINT chk_processing_status 
CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed'));

ALTER TABLE event_evidence 
ADD CONSTRAINT chk_access_level_evidence 
CHECK (access_level IN ('public', 'law_enforcement', 'admin', 'restricted'));

-- Create trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_event_updated_at 
    BEFORE UPDATE ON event 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_evidence_updated_at 
    BEFORE UPDATE ON event_evidence 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE event IS 'Event entity representing temporal interactions and status changes';
COMMENT ON COLUMN event.event_id IS 'Unique identifier for this event';
COMMENT ON COLUMN event.pfif_id IS 'Reference to person.pfif_id';
COMMENT ON COLUMN event.location_id IS 'Reference to location.location_id (optional)';
COMMENT ON COLUMN event.event_type IS 'sighting, police_report, status_change, tip, document, recovery';
COMMENT ON COLUMN event.event_date IS 'When the event occurred (actual time)';
COMMENT ON COLUMN event.reported_date IS 'When this event was reported to system';
COMMENT ON COLUMN event.source_type IS 'user_submitted, police_report, scraper, system_generated, media_report';
COMMENT ON COLUMN event.is_verified IS 'Verified by moderator or authority';
COMMENT ON COLUMN event.evidence_count IS 'Number of attached photos, documents, etc.';
COMMENT ON COLUMN event.has_media IS 'True if event has photos/audio/video';
COMMENT ON COLUMN event.ai_processed IS 'True if AI has processed this event';
COMMENT ON COLUMN event.ai_entities IS 'Entities extracted by AI (names, locations, dates)';
COMMENT ON COLUMN event.is_public IS 'False = law enforcement only';

COMMENT ON TABLE event_evidence IS 'Evidence and attachments for events';
COMMENT ON COLUMN event_evidence.evidence_type IS 'photo, video, audio, document, screenshot, text, url';
COMMENT ON COLUMN event_evidence.file_hash IS 'SHA-256 hash for deduplication';
COMMENT ON COLUMN event_evidence.is_public IS 'False = law enforcement only';
COMMENT ON COLUMN event_evidence.contains_pii IS 'Contains personally identifiable information';

-- Grant permissions (adjust as needed for your deployment)
-- GRANT SELECT, INSERT, UPDATE ON event TO opentrace_app;
-- GRANT SELECT, INSERT, UPDATE ON event_evidence TO opentrace_app;
-- GRANT USAGE ON SCHEMA public TO opentrace_app;
