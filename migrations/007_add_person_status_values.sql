-- Migration: Add additional allowed person status values
-- Adds 'died' and 'other' to the status check constraint and migrates common synonyms

-- 1) Map common synonyms (died, deceased, dead, passed) to 'died'
UPDATE person
SET status = 'died'
WHERE lower(status) IN ('died','deceased','dead','passed','passed away');

-- 2) Map any existing non-canonical status to 'other' (defensive)
UPDATE person
SET status = 'other'
WHERE lower(status) NOT IN ('missing','unidentified','found','died','other');

-- 3) Drop and recreate the CHECK constraint to include new values
ALTER TABLE person DROP CONSTRAINT IF EXISTS person_status_check;
ALTER TABLE person ADD CONSTRAINT person_status_check CHECK (status IN ('missing','unidentified','found','died','other'));

-- NOTE: Run this migration with: psql -f migrations/007_add_person_status_values.sql
