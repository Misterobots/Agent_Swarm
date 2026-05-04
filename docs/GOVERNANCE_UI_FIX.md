# Governance UI Fix - Permanent Solution

## Problem
The governance page at https://hive.shivelymedia.com/governance shows "No governance requests found" even though the backend has 7 historical requests.

### Root Cause
**Endpoint Mismatch**: The UI JavaScript calls `/api/backend/v1/request`, but after the Next.js proxy strips `/api/backend`, it becomes `/v1/request`. However, the backend routes are at `/api/v1/request`, causing 404 errors.

### Correct Flow
```
Browser → /api/backend/api/v1/request 
  ↓ Next.js proxy strips /api/backend
  ↓ /api/v1/request 
  ↓ Matches backend route
  ✓ Returns 7 governance requests
```

## The Fix

### File: `ui/src/lib/api/workspaces.ts`  
**Line 45**: Change from `/v1/request` to `/api/v1/request`

```typescript
export async function fetchGovernanceRequests(): Promise<GovernanceRequest[]> {
  const res = await fetch(`${API_BASE}/api/v1/request`);  // ← FIXED
  if (!res.ok) return [];
  return res.json();
}
```

**Status**: ✅ This file is already correct on both Lovelace and Turing

## Deployment Steps

### On Lovelace (already complete):
1. ✅ Source file has correct endpoint
2. ✅ All dev component files exist

### On Turing (needs completion):

#### Step 1: Verify source file is correct
```bash
ssh misterobots@192.168.2.103
grep -n '/api/v1/request' ~/Home_AI_Lab/ui/src/lib/api/workspaces.ts
# Should see line 45 with correct endpoint
```

#### Step 2: Handle dev components (choose ONE option):

**Option A: Copy stub files from Lovelace**
```bash
# From Lovelace PowerShell:
scp -r C:\Users\panca\Documents\Github\Agent_Swarm\ui\src\components\dev\*.tsx misterobots@192.168.2.103:~/Home_AI_Lab/ui/src/components/dev/
```

**Option B: Comment out dev page (if build fails)**
```bash
# On Turing:
ssh misterobots@192.168.2.103
cd ~/Home_AI_Lab/ui/src/app/dev
mv page.tsx page.tsx.bak
echo 'export default function DevPage() { return <div>Dev page disabled</div> }' > page.tsx
```

#### Step 3: Rebuild Docker image
```bash
ssh misterobots@192.168.2.103
cd ~/Home_AI_Lab/turing_gateway
docker compose build --no-cache hive-ui
docker compose up -d hive-ui
```

#### Step 4: Verify deployment
```bash
# Check container is running
docker ps | grep hive_ui

# Test endpoint directly
curl -s http://localhost:3200/api/backend/api/v1/request | jq length
# Should return: 7
```

#### Step 5: Test in browser
1. Open https://hive.shivelymedia.com/governance
2. Hard refresh (Ctrl+Shift+R or Ctrl+F5)
3. Clear browser cache if needed
4. Should see 7 governance requests displayed

## Verification

### Backend (already working):
```bash
curl http://192.168.2.103:8008/api/v1/request
# Returns 7 items with IDs: d4e6d8e9, 7865a546, fca00999, a9ac5738, dae37457, 969bb771, 1b08e85a
```

### Frontend (after fix):
- Browser console should show NO 404 errors for `/api/backend/v1/request`
- Table should display 7 requests with proper status counts
- Status filter buttons should show: "COMPLETED (5)", "APPROVED (2)", etc.

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Backend API | ✅ Working | Returns 7 requests correctly |
| workspaces.ts (Lovelace) | ✅ Fixed | Has correct `/api/v1/request` |
| workspaces.ts (Turing) | ✅ Fixed | Successfully copied from Lovelace |
| Dev components (Turing) | ⚠️ Missing | Blocking Docker build |
| Docker image rebuild | ❌ Not complete | Blocked by dev components |
| Live deployment | ❌ Not deployed | Still using old image with wrong endpoint |

## Why Manual Patches Don't Work

The sed patches I applied to running container JavaScript files are **lost on every container restart or rebuild** because:
1. Docker containers are immutable - files revert to image state on restart
2. The patches modify compiled output, not source code
3. No persistent storage for modified JavaScript files

**This is why a proper Docker image rebuild with corrected source code is required.**

## Next Steps

1. **Immediate**: Fix dev components issue on Turing (Option A or B above)
2. **Deploy**: Complete Docker rebuild with corrected source
3. **Test**: Verify governance page displays 7 requests
4. **Document**: Update deployment runbook with this fix

## Related Files

- `ui/src/lib/api/workspaces.ts` - API wrapper functions (FIXED)
- `agents/main.py` - Backend governance routes (working correctly)
- `agents/liskov.py` - Governance request manager (working correctly)
- `ui/src/app/governance/page.tsx` - Frontend page component
- `ui/src/app/api/backend/[...path]/route.ts` - Next.js proxy (working correctly)

## Timeline

- **Issue discovered**: May 3, 2026
- **Root cause identified**: Endpoint URL mismatch
- **Source fix applied**: May 3, 2026 (workspaces.ts corrected)
- **Deployment pending**: Blocked by build dependencies
- **Estimated time to fix**: 5 minutes once dev components resolved
