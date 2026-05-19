import psycopg2, os
conn = psycopg2.connect(os.environ['TEMPLATE_DB_URL'])
cur = conn.cursor()
# Fix run 38: the training actually used Qwen/Qwen2.5-Coder-7B-Instruct
cur.execute("UPDATE swarm.training_runs SET target_model = %s WHERE id = 38 AND target_model = %s",
            ("Qwen/Qwen2.5-Coder-7B-Instruct", "qwen2.5-coder:14b-instruct-q4_K_M"))
print(f"Updated {cur.rowcount} rows")
conn.commit()
cur.close()
conn.close()
