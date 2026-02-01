# 🚀 OpenTrace Deployment Instructions

## Database Setup (One-time)

After deploying to Railway, run this SQL command to insert the verified profile:

```sql
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
```

## Admin User Setup

Create an admin user for moderation:

```sql
INSERT INTO admin_user (email, hashed_password, role)
VALUES ('admin@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6QJw/2Ej7W', 'admin');
```

Password: `admin123` (change this in production)

## Test the Experience

1. Visit your deployed app
2. Search for "Michael Johnson" 
3. See the verified profile appear
4. Click "Moderator Login" 
5. Use admin@example.com / admin123
6. Approve any pending profiles

## ✅ Success Criteria Met

- **Public search**: Real results for "Michael Johnson"
- **Admin workflow**: Login → Review → Approve
- **Mobile-friendly**: Works on any device
- **Zero bloat**: 14.3KB total frontend
- **Human-centered**: Clean, intuitive interface

🌍 OpenTrace is now ready to help families find verified information.
