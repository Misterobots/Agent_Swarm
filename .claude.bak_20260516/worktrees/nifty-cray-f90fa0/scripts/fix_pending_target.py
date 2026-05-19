"""Fix training runs with 'pending' target_model by setting the correct model from config."""
import psycopg2
import os
import json
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "agents"))

TEMPLATE_DB_URL = os.environ.get("TEMPLATE_DB_URL", "")

def main():
    if not TEMPLATE_DB_URL:
        print("ERROR: TEMPLATE_DB_URL not set")
        return

    conn = psycopg2.connect(TEMPLATE_DB_URL)
    cur = conn.cursor()

    # Find runs with 'pending' target_model
    cur.execute("""
        SELECT id, target_model, status, run_type, metrics
        FROM swarm.training_runs
        WHERE target_model = 'pending'
        ORDER BY id
    """)
    rows = cur.fetchall()
    print(f"Found {len(rows)} runs with target_model='pending'")

    for run_id, target_model, status, run_type, metrics in rows:
        real_model = None
        if metrics:
            m = metrics if isinstance(metrics, dict) else json.loads(metrics)
            real_model = m.get("target_model")

        if real_model and real_model != "pending":
            print(f"  Run {run_id}: updating target_model from 'pending' -> '{real_model}'")
            cur.execute(
                "UPDATE swarm.training_runs SET target_model = %s WHERE id = %s",
                (real_model, run_id)
            )
        else:
            # Default to the standard base model
            default = "qwen2.5-coder:14b-instruct-q4_K_M"
            print(f"  Run {run_id}: no target_model in metrics, defaulting to '{default}'")
            cur.execute(
                "UPDATE swarm.training_runs SET target_model = %s WHERE id = %s",
                (default, run_id)
            )

    conn.commit()
    cur.close()
    conn.close()
    print("Done")

if __name__ == "__main__":
    main()
