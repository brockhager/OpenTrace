import os
import psycopg2

DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('RAILWAY_DATABASE_URL')
if not DATABASE_URL:
    print('DATABASE_URL not set')
    raise SystemExit(1)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
cur.execute("SELECT status, count(*) FROM person GROUP BY status ORDER BY status;")
rows = cur.fetchall()
print('Status counts:')
for r in rows:
    print(r[0], r[1])
cur.close()
conn.close()