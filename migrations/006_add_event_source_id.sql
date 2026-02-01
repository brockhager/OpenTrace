-- Migration: Add source_id to Event table (Phase 16)
-- This adds the foreign key from Event to Source for provenance tracking
-- Run this after deploying Source entity: psql -f migrations/006_add_event_source_id.sql

-- Add source_id column to event table
ALTER TABLE event 
ADD COLUMN source_id UUID,
ADD COLUMN event_timestamp TIMESTAMP WITH TIME ZONE;

-- Create index for source_id
CREATE INDEX idx_event_source_id ON event(source_id);

-- Add foreign key constraint (optional - allows NULL for legacy events)
-- Commented out to support gradual migration - uncomment when all events have source_id
-- ALTER TABLE event 
-- ADD CONSTRAINT fk_event_source 
-- FOREIGN KEY (source_id) REFERENCES source(source_id) ON DELETE SET NULL;

-- Backfill event_timestamp from event_date for existing records
UPDATE event 
SET event_timestamp = event_date 
WHERE event_timestamp IS NULL;

-- Add comments
COMMENT ON COLUMN event.source_id IS 'Reference to source.source_id for provenance tracking (Phase 16)';
COMMENT ON COLUMN event.event_timestamp IS 'ISO 8601 timestamp of event occurrence (traceability model)';

-- Grant permissions
-- GRANT SELECT, UPDATE ON event TO opentrace_app;
