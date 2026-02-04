import os
import psycopg2
from datetime import datetime

DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('RAILWAY_DATABASE_URL')
if not DATABASE_URL:
    print('DATABASE_URL not set')
    raise SystemExit(1)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

today = datetime.utcnow().isoformat()

def insert_person(pfif, given, family, status):
    try:
        cur.execute(
            """
            INSERT INTO person (pfif_id, given_name, family_name, status, is_confirmed, source_confidence, primary_source, source_url, is_active, data_sensitivity, entry_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (pfif, given, family, status, False, 'medium', 'test', 'https://example.com/test', True, 'standard', today)
        )
        conn.commit()
        print('Inserted', pfif)
    except Exception as e:
        conn.rollback()
        print('Failed to insert', pfif, '->', e)

insert_person('opentrace.org/person.test.PER-died-001', 'Test', 'Died', 'died')
insert_person('opentrace.org/person.test.PER-other-001', 'Test', 'Other', 'other')

cur.execute("SELECT pfif_id, status FROM person WHERE pfif_id LIKE 'opentrace.org/person.test.PER-%'")
rows = cur.fetchall()
print('Inserted test rows:')
for r in rows:
    print(r)

cur.close()
conn.close()