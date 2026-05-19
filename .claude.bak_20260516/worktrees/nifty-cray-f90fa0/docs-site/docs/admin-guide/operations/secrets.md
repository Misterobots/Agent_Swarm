---
title: Secrets Management
---

# Secrets Management

How credentials are managed across Memex nodes.

## Secret Categories

| Category | Examples | Storage |
|----------|----------|---------|
| **Database** | PostgreSQL password, MinIO credentials | `network.env` |
| **API Keys** | Langfuse keys, Authentik tokens | `network.env` |
| **SPIRE** | Join tokens, trust bundle | SPIRE server (ephemeral) |
| **OAuth** | Client secrets, redirect URIs | Authentik config |
| **TLS** | Certificates, private keys | Traefik auto-managed |

## network.env

The `network.env` file at the repository root contains all shared secrets. This file is **not committed to Git** (listed in `.gitignore`).

!!! danger "Security"
    - Never commit `network.env` to version control
    - Restrict file permissions: `chmod 600 network.env`
    - Use a password manager to store a backup
    - Rotate secrets periodically

### Structure

```bash
# Database
POSTGRES_PASSWORD=<strong-random-password>

# Langfuse
LANGFUSE_SECRET_KEY=<random-key>

# MinIO
MINIO_ROOT_USER=minio
MINIO_ROOT_PASSWORD=<strong-random-password>

# OAuth (Authentik)
AUTHENTIK_SECRET_KEY=<random-key>
```

## SPIRE Credentials

SPIRE uses **ephemeral join tokens** instead of static credentials:

1. Tokens are generated on the SPIRE Server
2. Each token is single-use
3. Tokens expire after TTL (default: 3600s)
4. After attestation, the agent receives an X.509 SVID

See [Procedure: Rotate SPIRE Keys](../../procedures/rotate-spire-keys.md) for rotation.

## Rotation Schedule

| Secret | Rotation | Procedure |
|--------|----------|-----------|
| PostgreSQL password | Quarterly | Update `network.env`, restart PG |
| Langfuse keys | Quarterly | Update `network.env`, restart Langfuse |
| SPIRE join tokens | Per-use | Generated fresh each time |
| OAuth client secrets | Annually | Regenerate in Authentik |
| TLS certificates | Auto | Traefik ACME auto-renewal |

## Related

- [Architecture: Security Model](../../architecture/security-model.md)
- [Procedures: Rotate SPIRE Keys](../../procedures/rotate-spire-keys.md)
- [Configuration: Environment](../configuration/environment.md)


