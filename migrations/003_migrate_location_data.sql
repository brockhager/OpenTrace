-- Migration: Extract and migrate location data from PersonProfile (Phase 14.1)
-- This migrates existing location data to the new Location entity structure
-- Run this after the location tables are created: psql -f migrations/003_migrate_location_data.sql

-- Step 1: Extract unique locations from PersonProfile
INSERT INTO location (
    location_id, canonical_name, display_name, latitude, longitude,
    coordinate_precision, country_code, country_name, admin1_name, admin2_name, locality,
    location_type, confidence_score, source_system, source_data
)
SELECT DISTINCT
    CASE 
        WHEN last_seen_location IS NOT NULL THEN 
            regexp_replace(lower(regexp_replace(last_seen_location, '[^a-zA-Z,\s]', '', 'g')), '[\s,]+', '-', 'g')
        ELSE 'unknown-location-' || md5(random()::text)
    END as location_id,
    
    COALESCE(last_seen_location, 'Unknown Location') as canonical_name,
    COALESCE(last_seen_location, 'Unknown Location') as display_name,
    
    -- Try to extract coordinates from source URLs (NamUs pattern)
    CASE 
        WHEN source_url ~ 'lat=([0-9.-]+)' THEN CAST(regexp_replace(source_url, '.*lat=([0-9.-]+).*', '\1') AS NUMERIC(10,8))
        WHEN last_seen_location ~* 'los angeles' THEN 34.0522
        WHEN last_seen_location ~* 'new york' THEN 40.7128
        WHEN last_seen_location ~* 'chicago' THEN 41.8781
        WHEN last_seen_location ~* 'houston' THEN 29.7604
        WHEN last_seen_location ~* 'phoenix' THEN 33.4484
        WHEN last_seen_location ~* 'philadelphia' THEN 39.9526
        WHEN last_seen_location ~* 'san antonio' THEN 29.4241
        WHEN last_seen_location ~* 'san diego' THEN 32.7157
        WHEN last_seen_location ~* 'dallas' THEN 32.7767
        WHEN last_seen_location ~* 'san jose' THEN 37.3382
        ELSE 39.8283  -- Default to US center
    END as latitude,
    
    CASE 
        WHEN source_url ~ 'lng=([0-9.-]+)' THEN CAST(regexp_replace(source_url, '.*lng=([0-9.-]+).*', '\1') AS NUMERIC(11,8))
        WHEN last_seen_location ~* 'los angeles' THEN -118.2437
        WHEN last_seen_location ~* 'new york' THEN -74.0060
        WHEN last_seen_location ~* 'chicago' THEN -87.6298
        WHEN last_seen_location ~* 'houston' THEN -95.3698
        WHEN last_seen_location ~* 'phoenix' THEN -112.0740
        WHEN last_seen_location ~* 'philadelphia' THEN -75.1652
        WHEN last_seen_location ~* 'san antonio' THEN -98.4936
        WHEN last_seen_location ~* 'san diego' THEN -117.1611
        WHEN last_seen_location ~* 'dallas' THEN -96.7970
        WHEN last_seen_location ~* 'san jose' THEN -121.8863
        ELSE -98.5795  -- Default to US center
    END as longitude,
    
    'approximate' as coordinate_precision,
    'US' as country_code,
    'United States' as country_name,
    
    -- Extract state information
    CASE 
        WHEN last_seen_location ~* ',\s*([A-Z]{2})\s*$' THEN upper(regexp_replace(last_seen_location, '.*,\s*([A-Z]{2})\s*$', '\1'))
        WHEN last_seen_location ~* 'california' THEN 'CA'
        WHEN last_seen_location ~* 'texas' THEN 'TX'
        WHEN last_seen_location ~* 'new york' THEN 'NY'
        WHEN last_seen_location ~* 'florida' THEN 'FL'
        WHEN last_seen_location ~* 'illinois' THEN 'IL'
        ELSE NULL
    END as admin1_code,
    
    CASE 
        WHEN last_seen_location ~* ',\s*([A-Z]{2})\s*$' THEN regexp_replace(last_seen_location, '.*,\s*([A-Z]{2})\s*$', '\1')
        WHEN last_seen_location ~* 'california' THEN 'California'
        WHEN last_seen_location ~* 'texas' THEN 'Texas'
        WHEN last_seen_location ~* 'new york' THEN 'New York'
        WHEN last_seen_location ~* 'florida' THEN 'Florida'
        WHEN last_seen_location ~* 'illinois' THEN 'Illinois'
        ELSE NULL
    END as admin1_name,
    
    -- Extract city information
    CASE 
        WHEN last_seen_location ~* '^([^,]+),' THEN regexp_replace(last_seen_location, '^([^,]+),.*', '\1')
        WHEN last_seen_location ~* 'los angeles' THEN 'Los Angeles'
        WHEN last_seen_location ~* 'new york' THEN 'New York'
        WHEN last_seen_location ~* 'chicago' THEN 'Chicago'
        WHEN last_seen_location ~* 'houston' THEN 'Houston'
        ELSE regexp_replace(SPLIT_PART(last_seen_location, ',', 1), '\s+', ' ')
    END as locality,
    
    'city' as location_type,
    0.6 as confidence_score,  -- Medium confidence for extracted data
    'person_profile_migration' as source_system,
    jsonb_build_object(
        'original_text', last_seen_location,
        'source_url', source_url,
        'author_name', author_name
    ) as source_data
    
FROM person_profile
WHERE last_seen_location IS NOT NULL 
   AND last_seen_location != ''
ON CONFLICT (location_id) DO NOTHING;

-- Step 2: Create person-location relationships for existing data
INSERT INTO person_location (
    pfif_id, location_id, event_type, event_date, event_description,
    source_url, source_confidence, is_verified, is_public, created_by
)
SELECT 
    pp.pfif_id,
    l.location_id,
    'last_seen' as event_type,
    CASE
        WHEN pp.source_date ~ '^\d{4}-\d{2}-\d{2}' THEN pp.source_date::timestamp
        WHEN pp.source_date ~ '^\d{1,2}/\d{1,2}/\d{4}' THEN to_timestamp(pp.source_date, 'MM/DD/YYYY')
        ELSE NULL
    END as event_date,
    'Migrated from PersonProfile last_seen_location' as event_description,
    pp.source_url,
    'medium' as source_confidence,
    pp.is_confirmed as is_verified,
    true as is_public,
    'migration_script' as created_by
    
FROM person_profile pp
JOIN location l ON (
    l.display_name = pp.last_seen_location OR
    l.canonical_name = pp.last_seen_location
)
WHERE pp.last_seen_location IS NOT NULL 
   AND pp.last_seen_location != ''
ON CONFLICT DO NOTHING;

-- Step 3: Update some sample locations with better coordinates for testing
UPDATE location SET 
    latitude = 34.0522,
    longitude = -118.2437,
    admin1_code = 'CA',
    admin1_name = 'California',
    locality = 'Los Angeles',
    confidence_score = 0.9
WHERE display_name ~* 'los angeles';

UPDATE location SET 
    latitude = 40.7128,
    longitude = -74.0060,
    admin1_code = 'NY',
    admin1_name = 'New York',
    locality = 'New York',
    confidence_score = 0.9
WHERE display_name ~* 'new york';

UPDATE location SET 
    latitude = 41.8781,
    longitude = -87.6298,
    admin1_code = 'IL',
    admin1_name = 'Illinois',
    locality = 'Chicago',
    confidence_score = 0.9
WHERE display_name ~* 'chicago';

-- Step 4: Create a sample location for Michael Johnson if it doesn't exist
INSERT INTO location (
    location_id, canonical_name, display_name, latitude, longitude,
    coordinate_precision, country_code, country_name, admin1_code, admin1_name,
    locality, location_type, confidence_score, source_system
) VALUES (
    'los-angeles-ca-usa',
    'Los Angeles, California, USA',
    'Los Angeles, CA',
    34.0522,
    -118.2437,
    'approximate',
    'US',
    'United States',
    'CA',
    'California',
    'Los Angeles',
    'city',
    0.95,
    'sample_data'
) ON CONFLICT (location_id) DO NOTHING;

-- Step 5: Link Michael Johnson to Los Angeles if he exists
INSERT INTO person_location (
    pfif_id, location_id, event_type, event_date, event_description,
    source_confidence, is_verified, is_public, created_by
) VALUES (
    'opentrace.org/person/namus.MP24398',
    'los-angeles-ca-usa',
    'last_seen',
    '2021-06-15T00:00:00Z',
    'Last seen in Los Angeles area',
    'high',
    true,
    true,
    'sample_migration'
) ON CONFLICT DO NOTHING;

-- Step 6: Verification queries
DO $$
DECLARE
    location_count INTEGER;
    person_location_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO location_count FROM location;
    SELECT COUNT(*) INTO person_location_count FROM person_location;
    
    RAISE NOTICE 'Migration Summary:';
    RAISE NOTICE '- Locations created: %', location_count;
    RAISE NOTICE '- Person-location relationships created: %', person_location_count;
    
    IF location_count = 0 THEN
        RAISE NOTICE 'WARNING: No locations were created. Check if person_profile table has last_seen_location data.';
    END IF;
    
    IF person_location_count = 0 THEN
        RAISE NOTICE 'WARNING: No person-location relationships were created.';
    END IF;
END $$;

-- Step 7: Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_location_migration_source ON location(source_system);
CREATE INDEX IF NOT EXISTS idx_person_location_migration_created ON person_location(created_by);

COMMIT;
