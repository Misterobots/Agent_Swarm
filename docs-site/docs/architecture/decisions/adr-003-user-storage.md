---
title: "ADR-003: Filesystem User Storage"
---

# ADR-003: Filesystem User Storage

**Status**: Accepted  
**Date**: 2025-12

## Context

Memex stores persistent data per user: session histories, learned rules, preferences, generated artifacts (images, 3D models), and project files. Options considered:

1. **Database-only**: Store everything in PostgreSQL
2. **Object storage**: Use MinIO for all user data
3. **Filesystem**: Local filesystem organized by user/project

## Decision

Use **filesystem-based user storage** with Docker volume mounts for persistence.

### Directory Structure

```
/workspace/
├── agents/
│   ├── skills_memory.json        # Learned rules
│   └── context_sessions/         # Active sessions
├── user_projects/
│   └── {project_name}/          # User project files
├── delivered_artifacts/
│   ├── images/                  # Generated images
│   ├── 3d/                      # Generated 3D models
│   └── code/                    # Generated code artifacts
└── training_data/
    ├── comparisons/             # A/B test results
    └── sessions/                # GRPO training data
```

### Why Filesystem

- User projects are files — code, configs, scripts. A filesystem is the natural storage medium
- OpenHands and ComfyUI already operate on filesystem paths
- Docker volumes provide persistence across container restarts
- Easy to backup (tar/rsync) and inspect (ls/cat)

## Consequences

### Positive

- **Natural fit**: Code and config files live on the filesystem
- **Tool compatibility**: All tools (ComfyUI, OpenHands, Git) work natively with files
- **Simple backups**: `tar` or `rsync` the volume
- **Inspectable**: SSH in and `cat` any file for debugging
- **No ORM**: No need to serialize/deserialize from a database

### Negative

- **No built-in versioning**: Must layer Git or manual backups for history
- **Concurrent access**: No ACID transactions on file writes
- **No search**: Filesystem search is slower than database queries (mitigated by MemPalace for semantic search)
- **Volume management**: Docker volumes must be backed up separately from database dumps

## Related

- [Architecture: Memory System](../memory-system.md)
- [Admin: Backup and Restore](../../admin-guide/operations/backup-restore.md)


