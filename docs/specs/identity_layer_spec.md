# Specification: Identity Layer (MAESTRO L7)

**Version**: 1.0
**Date**: 2026-02-04
**Status**: Implemented

## 1. Overview

The Identity Layer enforces strict authentication for all external entities (IDEs, CI/CD pipelines) communicating with the Agent Swarm. It moves beyond "trusting the network" to "trusting the credential".

## 2. Architecture

### 2.1 Credential Injection

- **Source**: Docker Compose (`execution_plane/docker-compose.yml`)
- **Mechanism**: Environment Variables
  - `agent-runtime`: `VALID_API_KEYS={"key": "identity"}`
  - `agent_ide_coding`: `SWARM_API_KEY=sk-coder-...`
- **Security**: Secrets are not committed to code (except dev defaults in this repo).

### 2.2 Transport Security

- **Protocol**: HTTP (Internal Docker Network)
- **Header**: `X-Swarm-Source` containing the API Key.

### 2.3 Enforcement Logic

- **Component**: `agents/main.py` (FastAPI)
- **Flow**:
  1.  Request arrives at `/api/v1/request`.
  2.  `create_request` handler extracts `X-Swarm-Source`.
  3.  Validates key against loaded `VALID_API_KEYS`.
  4.  If Valid -> Resolves `user_id` (e.g. `coding_user`).
  5.  If Invalid -> Returns 401 Unauthorized.
  6.  System forwards resolved `user_id` to Governance Manager.

## 3. Data Model

### API Key Map

```json
{
  "sk-coder-identity": "coding_user",
  "sk-devops-identity": "devops_user"
}
```

## 4. Usage

### Client (Python)

```python
import os, urllib.request
headers = {'X-Swarm-Source': os.getenv('SWARM_API_KEY')}
req = urllib.request.Request(url, headers=headers)
```
