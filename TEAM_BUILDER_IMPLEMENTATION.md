# Team Builder & Role-Based Model Routing — Implementation Guide

## Status: 95% Complete ✅

### What's Been Implemented

#### 1. **Core Infrastructure** ✅
- **[agents/config.py](agents/config.py)**: Added role-specific model environment variables
  - `CODER_MODEL`, `DEVOPS_MODEL`, `RESEARCHER_MODEL`, `ANALYST_MODEL`, `VERIFIER_MODEL`
  - All default to `ARCHITECT_MODEL` for backward compatibility

#### 2. **Coordinator Mode Integration** ✅
- **[agents/lamport.py](agents/lamport.py)**: Updated `_get_agent_for_role()`
  - Maps each role to its configured model
  - Passes role-specific models to `leibniz_agent.get_architect_agent(model_name=...)`
  - Uses role-specific models for all worker agents (researcher, analyst, verifier, etc.)

#### 3. **Docker Configuration** ✅
- **[turing_gateway/docker-compose.yml](turing_gateway/docker-compose.yml)**: Added environment variables
  - Smart defaults: `${CODER_MODEL:-${ARCHITECT_MODEL:-qwen3:8b}}`
  - No rebuild required — Python-only changes

#### 4. **Backend API** ✅
- **[agents/team_builder.py](agents/team_builder.py)**: Storage module
  - Stores user configs as JSON: `/workspace/user_projects/{uid}/team_config.json`
  - Functions: `get_team_config()`, `save_team_config()`, `get_model_for_role()`
  - Validates role names against `VALID_ROLES` set

- **[agents/main.py](agents/main.py)**: API endpoints
  - `GET /api/v1/team-builder/config` — Load user's configuration
  - `POST /api/v1/team-builder/config` — Save configuration
  - `DELETE /api/v1/team-builder/config` — Reset to defaults
  - Respects user identity from `X-authentik-uid` header

#### 5. **Frontend UI** ✅
- **[ui/src/components/settings/team-builder.tsx](ui/src/components/settings/team-builder.tsx)**: Team Builder component
  - Role cards with model dropdown selectors
  - 4 preset profiles: All Local, Hybrid, Max Quality, Speed Optimized
  - Real-time model list from Ollama API
  - Save/load configuration with status messages
  - Helpful tips for each role

- **[ui/src/app/settings/page.tsx](ui/src/app/settings/page.tsx)**: Integrated into settings
  - Added "Team Builder" section after "Provider API Keys"
  - Imported `TeamBuilderSettings` component

#### 6. **Helper Module** ✅
- **[agents/role_model_resolver.py](agents/role_model_resolver.py)**: Resolution logic
  - `get_model_for_role(uid, role, default)` helper function
  - Priority: Team config → Env var → Default → ARCHITECT_MODEL
  - Clean separation of concerns for church.py integration

#### 7. **Documentation** ✅
- **[.env.role-model.example](.env.role-model.example)**: Comprehensive configuration guide
  - 4 example profiles with full explanations
  - Node topology reference (Lovelace, Turing, Hopper specs)
  - Model recommendations per role
  - GPU routing explained

### What's Remaining

#### 8. **Dev Mode Integration** (15 minutes remaining) 🔨
Need to update **[agents/church.py](agents/church.py)** to use team builder in dev mode:

```python
# At top of file, add import:
from role_model_resolver import get_model_for_role

# In chat_swarm() function, extract uid early:
uid = None  # Extract from request headers or session

# Replace hardcoded model selections with:
# OLD:
DEVOPS_MODEL = os.getenv("ARCHITECT_MODEL", "qwen3:14b")

# NEW:
DEVOPS_MODEL = get_model_for_role(uid, "devops", default=DEVOPS_MODEL)
```

**Target locations in church.py:**
1. Line ~1735: DEVOPS intent handler
2. Line ~1820: DATA intent handler (use "analyst" role)
3. Line ~2425: Standard ARCHITECT/CODE intent (use "coder" role)
4. Line ~1900: IMAGE intent (use "architect" role)

### Testing Checklist

- [ ] **Test API endpoints**:
  ```bash
  curl http://192.168.2.103/hive/api/backend/v1/team-builder/config
  ```

- [ ] **Test UI**:
  1. Navigate to http://hive.shivelymedia.com/settings
  2. Scroll to "Team Builder" section
  3. Select models for each role
  4. Click "Save Config"
  5. Reload page and verify persistence

- [ ] **Test coordinator mode**:
  1. Set `CODER_MODEL=qwen2.5-coder:14b` in env
  2. Ask: "Use coordinator mode to build a REST API"
  3. Check logs for model assignments: `docker logs agent_runtime | grep "model:"`

- [ ] **Test dev mode** (after church.py integration):
  1. Enable developer mode in chat
  2. Ask: "Help me write a Python script"
  3. Verify coder role uses CODER_MODEL

### Deployment Instructions

#### Option A: Quick Test (Lovelace Only)
```powershell
# Set environment variables (temporary)
$env:CODER_MODEL = "qwen2.5-coder:14b"
$env:DEVOPS_MODEL = "qwen3:8b"
$env:RESEARCHER_MODEL = "llama3.2:3b"

# Restart agent runtime (no rebuild needed!)
C:\Windows\System32\OpenSSH\ssh.exe misterobots@192.168.2.103 `
  "cd /home/misterobots/Home_AI_Lab/turing_gateway && docker compose restart agent-runtime"
```

#### Option B: Permanent Configuration (Recommended)
```bash
# SSH to Turing
ssh misterobots@192.168.2.103

# Create .env file
cd /home/misterobots/Home_AI_Lab/turing_gateway
cat > .env << 'EOF'
# Core models
PRIMARY_MODEL=qwen3:8b
COORDINATOR_MODEL=qwen3:14b

# Role-specific models (Team Builder defaults)
CODER_MODEL=qwen2.5-coder:14b
DEVOPS_MODEL=qwen3:8b
RESEARCHER_MODEL=llama3.2:3b
ANALYST_MODEL=qwen3:8b
VERIFIER_MODEL=qwen3:8b
EOF

# Restart services
docker compose restart agent-runtime hive-ui
```

### Benefits

1. **No rebuild required** — Pure Python configuration changes
2. **Per-user customization** — Each user can have their own team
3. **UI-driven** — Non-technical users can configure via settings page
4. **Backward compatible** — Works with existing env var setup
5. **Flexible fallbacks** — Team config → Env → Default → Global

### Example Configurations

#### Profile: Local Only (No API Costs)
- **Coordinator**: qwen3:14b (task decomposition)
- **Coder**: qwen2.5-coder:14b (code generation)
- **DevOps**: qwen3:8b (scripts, Docker)
- **Researcher**: llama3.2:3b (fast context gathering)
- **Analyst**: qwen3:8b (data analysis)
- **Verifier**: qwen3:8b (code review)

#### Profile: Hybrid (Best Bang for Buck)
- **Coordinator**: qwen3:14b (local)
- **Coder**: claude-sonnet-4-6 (☁️ API, high quality)
- **DevOps**: nemotron:70b (Lovelace dual 5060 Ti)
- **Researcher**: llama3.2:3b (local, fast)
- **Analyst**: qwen3:8b (local)
- **Verifier**: claude-sonnet-4-6 (☁️ API, catches edge cases)

### Architecture Flow

```
User Request → church.py
    ↓
role_model_resolver.get_model_for_role(uid, "coder")
    ↓
1. Check team_builder.py → /workspace/user_projects/{uid}/team_config.json
2. Check environment variable → CODER_MODEL
3. Check default parameter
4. Fallback to ARCHITECT_MODEL
    ↓
Selected Model → Ollama/Cloud Provider → Response
```

### Files Changed

1. `agents/config.py` — Added 5 new role model env vars
2. `agents/lamport.py` — Updated _get_agent_for_role()
3. `turing_gateway/docker-compose.yml` — Added env vars to agent-runtime
4. `agents/team_builder.py` — NEW: User config storage
5. `agents/main.py` — Added 3 API endpoints
6. `agents/role_model_resolver.py` — NEW: Resolution helper
7. `ui/src/components/settings/team-builder.tsx` — NEW: UI component
8. `ui/src/app/settings/page.tsx` — Added Team Builder section
9. `.env.role-model.example` — NEW: Configuration guide
10. `agents/church.py` — PARTIAL: Imports added, intent handlers TODO

### Next Steps

1. **Complete church.py integration** (15 min):
   - Import role_model_resolver
   - Extract uid from request
   - Update DEVOPS, DATA, CODE, IMAGE intent handlers
   
2. **Test end-to-end** (20 min):
   - API endpoints
   - UI component
   - Coordinator mode routing
   - Dev mode routing

3. **Deploy to Turing** (5 min):
   - Copy files via rsync/scp
   - Restart agent_runtime container
   - Test via Hive UI

4. **User Documentation** (10 min):
   - Add Team Builder docs to docs-site
   - Create tutorial video/GIF
   - Update README

**Total Time to Complete: ~1 hour** ⏱️
