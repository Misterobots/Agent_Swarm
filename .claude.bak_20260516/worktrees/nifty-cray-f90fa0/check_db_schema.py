#!/usr/bin/env python3
"""Check provider_api_keys table schema"""
import psycopg2

conn = psycopg2.connect(
    host="192.168.2.102",
    port=5432,
    database="langfuse",
    user="langfuse",
    password="langfuseshively"
)

cur = conn.cursor()

# Check schema
cur.execute("""
    SELECT column_name, data_type, is_nullable 
    FROM information_schema.columns 
    WHERE table_schema = 'swarm' AND table_name = 'provider_api_keys'
    ORDER BY ordinal_position;
""")

print("=== Table Schema ===")
for row in cur.fetchall():
    print(f"  {row[0]:<15} {row[1]:<15} nullable={row[2]}")

# Check data
cur.execute("""
    SELECT user_id, provider, key_id, label, is_default
    FROM swarm.provider_api_keys
    ORDER BY provider, is_default DESC;
""")

print("\n=== Current Data ===")
rows = cur.fetchall()
if not rows:
    print("  (no data)")
else:
    for row in rows:
        print(f"  user={row[0][:8]}... provider={row[1]} key_id={row[2][:8] if row[2] else 'NULL'}... label={row[3]} default={row[4]}")

cur.close()
conn.close()
