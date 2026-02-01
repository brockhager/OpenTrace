-- Insert a single, approved NamUs profile for demo purposes
INSERT INTO person_profile (
  pfif_id, author_name, given_name, family_name, age, sex, last_seen_location, status, is_confirmed, source_date, profile_url
) VALUES (
  'opentrace.org/person.namus.MP12345',
  'NamUs',
  'Michael',
  'Johnson',
  42,
  'Male',
  'Los Angeles, CA',
  'missing',
  TRUE,
  '2018-06-01',
  'https://namus.nij.ojp.gov/case/MP12345'
);

-- Use:
-- railway run psql -c "\i scripts/insert_sample_profile.sql"