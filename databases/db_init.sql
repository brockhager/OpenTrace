-- Canonical missing persons profiles (PFIF 'person')
CREATE TABLE person_profile (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pfif_id TEXT UNIQUE NOT NULL,
  entry_date TIMESTAMPTZ DEFAULT NOW(),
  source_url TEXT, -- e.g., NamUs case URL
  author_name TEXT DEFAULT 'Community',
  given_name TEXT,
  family_name TEXT,
  alternate_names TEXT[], -- Array of aliases
  age INT,
  sex TEXT,
  last_seen_location TEXT,
  status TEXT DEFAULT 'missing' CHECK (status IN ('missing', 'unidentified', 'found')),
  is_confirmed BOOLEAN DEFAULT FALSE,
  expiry_date TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '1 year'),
  source_date TEXT, -- From PFIF
  profile_url TEXT -- Direct link to source
);

-- Intel items (user-submitted tips)
CREATE TABLE intel_item (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  person_pfif_id TEXT REFERENCES person_profile(pfif_id) ON DELETE CASCADE,
  entry_date TIMESTAMPTZ DEFAULT NOW(),
  author_name TEXT, -- Anonymous submitter ID
  source_url TEXT NOT NULL,
  text TEXT,
  category TEXT CHECK (category IN ('photo', 'social_profile', 'sighting', 'associate')),
  confidence_rating TEXT DEFAULT 'low' CHECK (confidence_rating IN ('low', 'medium', 'high')),
  reviewed BOOLEAN DEFAULT FALSE
);

-- Profile links (admin decisions)
CREATE TABLE profile_link (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  intel_id UUID REFERENCES intel_item(id) ON DELETE CASCADE,
  profile_id UUID REFERENCES person_profile(id) ON DELETE CASCADE,
  decision TEXT NOT NULL CHECK (decision IN ('confirmed', 'rejected', 'duplicate')),
  justification TEXT
);

-- Audit log for compliance
CREATE TABLE audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  action TEXT NOT NULL,
  actor_id TEXT,
  target_id UUID,
  timestamp TIMESTAMPTZ DEFAULT NOW(),
  details JSONB
);

-- Admin users for authentication
CREATE TABLE admin_user (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  hashed_password TEXT NOT NULL,
  role TEXT CHECK (role IN ('admin', 'trusted_partner')) DEFAULT 'admin',
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_admin_email ON admin_user(email);

-- Indexes
CREATE INDEX ix_person_profile_pfif_id ON person_profile(pfif_id);
CREATE INDEX ix_intel_unreviewed ON intel_item(reviewed) WHERE reviewed = FALSE;
CREATE INDEX ix_audit_target ON audit_log(target_id);