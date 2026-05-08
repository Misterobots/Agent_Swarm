---
title: "MemPalace Migrations"
---

# MemPalace Migrations

!!! note "Pass 2 stub"
    Full Alembic workflow (creating migrations, baseline-stamping a live DB,
    deploy procedure) will be populated in Pass 2 of the documentation update.

For now, the high-level workflow is:

```bash
# Add a new migration after editing the ORM models
alembic revision --autogenerate -m "describe the change"

# Review the generated file (especially for pgvector type rendering)
$EDITOR control_plane/mempalace/alembic/versions/000N_*.py

# Migrations apply automatically on container boot via init_db()
```

For Alembic adoption against a live DB that already has tables, run
`alembic stamp 0001_baseline` once before deploying the new image.

See:

- [Architecture Deep Dive — Schema Migrations](../architecture/mempalace-deep-dive.md#schema-migrations)
- [Service: MemPalace](../modules/services/mempalace.md)
- [`control_plane/mempalace/alembic/`](https://github.com/Misterobots/Agent_Swarm/tree/main/control_plane/mempalace/alembic)
