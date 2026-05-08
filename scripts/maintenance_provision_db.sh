#!/usr/bin/env bash
# Provision the maintenance Postgres role + database on Hopper (192.168.2.102).
#
# The maintenance_router auto-creates its own tables (maintenance_dispatch,
# maintenance_queue) on first connect; this script only handles what requires
# superuser: the role and the empty database.
#
# Run from a machine that can reach Hopper's Postgres on :5432, with PGPASSWORD
# (or .pgpass) set for the postgres superuser. Or scp this to Hopper and run
# locally as the postgres OS user.
#
# Idempotent: re-running is safe.

set -euo pipefail

MAINT_DB="${MAINTENANCE_DB_NAME:-maintenance}"
MAINT_USER="${MAINTENANCE_DB_USER:-maintenance}"
MAINT_PASS="${MAINTENANCE_DB_PASSWORD:?Set MAINTENANCE_DB_PASSWORD before running}"
PG_HOST="${PG_SUPERUSER_HOST:-192.168.2.102}"
PG_PORT="${PG_SUPERUSER_PORT:-5432}"
PG_USER="${PG_SUPERUSER_USER:-postgres}"

psql_super() {
  PGPASSWORD="${PGPASSWORD:-}" psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -v ON_ERROR_STOP=1 "$@"
}

echo "Creating role $MAINT_USER (if missing)..."
psql_super -d postgres <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$MAINT_USER') THEN
    CREATE ROLE "$MAINT_USER" LOGIN PASSWORD '$MAINT_PASS';
  ELSE
    ALTER ROLE "$MAINT_USER" WITH LOGIN PASSWORD '$MAINT_PASS';
  END IF;
END
\$\$;
SQL

echo "Creating database $MAINT_DB (if missing)..."
EXISTS=$(psql_super -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$MAINT_DB'")
if [[ "$EXISTS" != "1" ]]; then
  psql_super -d postgres -c "CREATE DATABASE \"$MAINT_DB\" OWNER \"$MAINT_USER\";"
else
  psql_super -d postgres -c "ALTER DATABASE \"$MAINT_DB\" OWNER TO \"$MAINT_USER\";"
fi

echo "Granting privileges..."
psql_super -d "$MAINT_DB" <<SQL
GRANT ALL ON SCHEMA public TO "$MAINT_USER";
SQL

echo "Done. The router will auto-create its tables on first connect."
echo "Verify with:"
echo "  PGPASSWORD='<pw>' psql -h $PG_HOST -U $MAINT_USER -d $MAINT_DB -c '\\dt'"
