# Memex (Agent Swarm)

A self-hosted, distributed multi-agent AI system for home automation, coding, creative media, and voice interaction. All inference runs on-premises — no external AI services.

## Documentation

- **Full documentation**: [memex.shivelymedia.com/docs-site](https://memex.shivelymedia.com/docs-site/) (SSO required) — user guides, architecture, admin/deployment, security, procedures, troubleshooting, reference.
- **Session/infra primer**: [CLAUDE.md](CLAUDE.md) — network map, repository layout, deployment gotchas. Authoritative for current infrastructure state.
- **Governance & compliance records**: [docs/INDEX.md](docs/INDEX.md) — audit trail, ADRs, MAESTRO compliance status, evidence.

## Repository Layout

- `agents/` — Python agent runtime (router, coordinator, specialized agents, tools)
- `ui/` — Next.js frontend
- `docs-site/` — the canonical MkDocs documentation site (source for the link above)
- `docs/` — governance, compliance, and audit-trail records (not product docs)
- `execution_plane/`, `turing_gateway/` — deployment compose files and gateway config

See [CLAUDE.md](CLAUDE.md) for the full architecture, network topology, and deployment workflow.

---

_Memex · Self-hosted · Private inference · No cloud dependencies_
