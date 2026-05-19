import psycopg2, os, json
conn = psycopg2.connect(os.environ['TEMPLATE_DB_URL'])
cur = conn.cursor()
cur.execute('SELECT id, target_model, status, run_type, metrics FROM swarm.training_runs ORDER BY id DESC LIMIT 5')
for r in cur.fetchall():
    m = r[4] if isinstance(r[4], dict) else (json.loads(r[4]) if r[4] else {})
    print(f'Run {r[0]}: model={r[1]}, status={r[2]}, type={r[3]}, adapter={m.get("adapter_path", "NONE")}')
cur.close()
conn.close()
