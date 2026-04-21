---
title: "Troubleshooting: Langfuse"
---

# Langfuse Troubleshooting

## Langfuse Dashboard Not Loading

**Symptom**: `http://{{ hopper_ip }}:3000` doesn't respond.

**Diagnose**:

```bash
docker compose ps langfuse
docker logs langfuse --tail 30
```

**Fix**:

- Check PostgreSQL is running (Langfuse depends on it)
- Verify `LANGFUSE_DATABASE_URL` in environment
- Restart: `docker compose restart langfuse`

---

## Traces Not Appearing

**Symptom**: Conversations happen but no traces in Langfuse.

**Diagnose**:

Check agent runtime logs for Langfuse connection errors.

**Fix**:

1. Verify `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` in `network.env`
2. Test connectivity from agent runtime: `curl http://{{ hopper_ip }}:3000/api/public/health`
3. Check that the Langfuse SDK is initialized in the agent code

---

## Database Connection Errors

**Symptom**: Langfuse logs show PostgreSQL connection refused.

**Fix**:

1. Verify PostgreSQL is running: `docker compose ps postgres`
2. Check credentials in Langfuse environment variables
3. Verify the database exists:
   ```bash
   docker compose exec postgres psql -U postgres -l
   ```

---

## High Disk Usage

**Symptom**: PostgreSQL database growing very large from traces.

**Fix**:

1. Set a retention policy in Langfuse settings
2. Archive old traces
3. Vacuum the database:
   ```bash
   docker compose exec postgres psql -U postgres -c "VACUUM FULL;"
   ```


