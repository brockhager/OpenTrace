-- Insert one verified profile for magical first-user experience
-- Run this on Railway PostgreSQL database after deployment

INSERT INTO person_profile (
  pfif_id, 
  author_name, 
  given_name, 
  family_name, 
  age, 
  sex,
  last_seen_location, 
  status, 
  is_confirmed, 
  source_date, 
  profile_url
) VALUES (
  'opentrace.org/person.namus.MP24398',
  'NamUs',
  'Michael',
  'Johnson',
  34,
  'Male',
  'Los Angeles, California',
  'missing',
  true,
  '2024-01-15',
  'https://www.namus.gov/MissingPersons/Case#24398'
);
