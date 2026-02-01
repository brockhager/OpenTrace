-- Canonical missing persons profiles (PFIF 'person')
CREATE TABLE person_profile (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pfif_id TEXT UNIQUE NOT NULL, -- e.g., "opentrace.org/person.123"
  entry_date TIMESTAMPTZ DEFAULT NOW(),
  source_url TEXT, -- e.g., NamUs case URL
  author_name TEXT DEFAULT 'Community', -- 'NamUs', 'Interpol', etc.
  full_name TEXT,
  age INT,
  sex TEXT,
  given_name TEXT,
  family_name TEXT,
  alternate_names TEXT[], -- Array of aliases
  source_date DATE,       -- From PFIF 'source_date'
  profile_url TEXT        -- Direct link to source (NamUs/Interpol)
);

-- Intel items (user-submitted tips)
CREATE TABLE intel_item (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pfif_id TEXT REFERENCES person_profile(pfif_id) ON DELETE CASCADE,
  source_url TEXT NOT NULL,
  text TEXT,
  reviewed BOOLEAN DEFAULT FALSE,
  submitted_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit log for compliance
CREATE TABLE audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  action TEXT NOT NULL,
  details JSONB,
  ip_address INET,
  performed_at TIMESTAMPTZ DEFAULT NOW()
);