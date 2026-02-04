import os
import sys
import psycopg2
from urllib.parse import urlparse

SQL_FILE = os.path.join(os.path.dirname(__file__), '..', 'migrations', '007_add_person_status_values.sql')

DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('RAILWAY_DATABASE_URL')
if not DATABASE_URL:
    print('DATABASE_URL not set in environment')
    sys.exit(1)

print('Using DATABASE_URL:', DATABASE_URL)

with open(SQL_FILE, 'r', encoding='utf-8') as f:
    sql = f.read()

# psycopg2 expects a postgres:// URL, so use as-is
try:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(sql)
    print('Migration executed successfully')
    cur.close()
    conn.close()
except Exception as e:
    print('Migration failed:', e)
    sys.exit(2)
