# Technical Debt & Future Improvements

## 🐳 Containerization (HIGH PRIORITY)

### Issue: ComfyUI Not Containerized
**Date Identified**: 2026-04-29  
**Impact**: Medium-High

**Problem**:
ComfyUI is currently running as a native Windows process on Lovelace, breaking the containerized architecture principle. This creates:
- Manual setup requirements
- Inconsistent deployment model
- No unified startup/shutdown
- Portability issues

**Current State**:
```
Lovelace (Windows PC):
  ❌ ComfyUI: Native Python process (python.exe)
  
Turing (Linux Server):
  ✅ agent_runtime: Docker container
  ✅ hive_ui: Docker container
  
Hopper (Linux Server):
  ✅ PostgreSQL: Docker container
  ✅ Redis: Docker container
  ✅ Langfuse: Docker container
  ✅ MemPalace: Docker container
```

**Desired State**:
```
All nodes: Everything in Docker containers
Startup: docker-compose up (or unified script)
Shutdown: docker-compose down
Management: Consistent across all Pioneer nodes
```

**Solution**:
1. Create `Dockerfile` for ComfyUI
2. Add ComfyUI service to docker-compose.yml
3. Configure NVIDIA GPU passthrough:
   ```yaml
   services:
     comfyui:
       image: comfyui:latest
       deploy:
         resources:
           reservations:
             devices:
               - driver: nvidia
                 count: all
                 capabilities: [gpu]
       ports:
         - "8188:8188"
       volumes:
         - ./models:/app/models
         - ./output:/app/output
   ```
4. Test on Windows Docker Desktop with WSL2
5. Document GPU setup for each OS

**Workaround (Current)**:
- Manual startup via `start_comfyui.bat`
- Optional Windows service via NSSM
- Document in setup procedures

**Priority**: HIGH (breaks architectural consistency)  
**Effort**: Medium (3-5 hours)  
**Assigned**: Unassigned  

---

## 📋 Other Technical Debt Items

### Media Archival Automation Not Scheduled
**Date**: 2026-04-29  
**Priority**: Low  
**Status**: Code complete, needs cron/Task Scheduler setup

Scripts created but not activated:
- `scripts/media_archiver.py` ✅
- `scripts/setup_media_archiver_cron.sh` ✅
- `scripts/setup_media_archiver_task.ps1` ✅

**Action**: Run setup scripts on production nodes

---

### Frontend Deployment Verification
**Date**: 2026-04-29  
**Priority**: Medium  
**Status**: Needs testing

Frontend media components deployed but not tested end-to-end:
- MediaPreview component
- media_attachment event handling
- Download functionality

**Action**: Test image generation with inline preview in production

---

## 🎯 Architectural Principles (Violations to Track)

1. **All services MUST be containerized**
   - Current violation: ComfyUI native process
   
2. **Single-command deployment**
   - Target: `docker-compose up` brings up entire stack
   - Current: Requires manual ComfyUI startup

3. **Configuration in version control**
   - All docker-compose files in Git ✅
   - All environment files templated ✅

4. **Unified logging**
   - All containers log to stdout ✅
   - ComfyUI logs to filesystem ❌

5. **Health checks for all services**
   - Most services have health checks ✅
   - ComfyUI has no health check ❌

---

## 📝 Notes

This document tracks technical debt and architectural deviations. Items should be:
- Reviewed quarterly
- Prioritized by impact × effort
- Assigned to milestone releases
- Resolved systematically (not accumulated)

**Last Updated**: 2026-04-29
