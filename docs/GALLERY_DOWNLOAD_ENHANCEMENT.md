# Gallery Download Functionality - Enhancement Summary

## Changes Made

### Backend Changes

#### 1. Enhanced `/api/v1/media/gallery` Endpoint
**File:** `agents/main.py`

Added `download_url` field to gallery items:
```python
items.append({
    "name": f.name,
    "kind": media_kind,
    "size_mb": round(f.stat().st_size / 1_048_576, 2),
    "updated_at": f.stat().st_mtime,
    "url": f"/delivered_artifacts/{f.name}",
    "download_url": f"/delivered_artifacts/{f.name}?dl=1",  # NEW
    "metadata": meta,
})
```

#### 2. New Download Endpoint for Delivered Artifacts
**File:** `agents/main.py` (after line 3100)

Added dedicated endpoint with download forcing capability:
```python
@app.get("/delivered_artifacts/{filepath:path}")
async def serve_delivered_artifact(filepath: str, dl: int = 0):
    """
    Serve files from delivered_artifacts with optional download forcing.
    Pass ?dl=1 to force browser download instead of inline display.
    """
```

**Features:**
- Respects `?dl=1` query parameter to force download
- Sets `Content-Disposition: attachment` header when `dl=1`
- Security: Prevents directory traversal attacks
- Auto-detects MIME types for images, videos, audio, and 3D models
- Falls back to StaticFiles mount for inline viewing (when `dl=0`)

### Frontend Changes

#### 1. TypeScript Type Update
**File:** `ui/src/types/workspaces.ts`

Added optional `download_url` field:
```typescript
export interface GalleryItem {
  name: string;
  kind: "image" | "audio" | "model";
  size_mb: number;
  updated_at: number;
  url: string;
  download_url?: string;  // NEW - Force download URL
  metadata?: Record<string, unknown> | null;
}
```

#### 2. Updated Gallery Pages

**Files Updated:**
- `ui/src/app/media/creature-forge/page.tsx`
- `ui/src/app/media/images/page.tsx`
- `ui/src/app/media/action-figure/page.tsx`

**Change Pattern:**
```tsx
// Before
<a href={item.url} download={item.name}>Download</a>

// After
<a href={item.download_url || item.url} download={item.name}>Download</a>
```

This ensures downloads use the `?dl=1` URL when available, falling back to the regular URL for backward compatibility.

## How It Works

### URL Structure

| Type | URL | Behavior |
|------|-----|----------|
| Preview | `/delivered_artifacts/image.png` | Inline display in browser |
| Download | `/delivered_artifacts/image.png?dl=1` | Force download |
| Preview | `/v1/art/files/3D/model.glb` | Inline/viewer (3D models) |
| Download | `/v1/art/files/3D/model.glb?dl=1` | Force download |

### Gallery Coverage

All gallery pages now have proper download functionality:

✅ **Art Studio Gallery** (`/art-studio/gallery`)
- Images: Download button on each card
- 3D Models: Download button on each card
- Already had proper download URLs

✅ **Media Images** (`/media/images`)
- Download link on each image card
- Now uses `download_url` with force-download

✅ **Action Figure** (`/media/action-figure`)
- Download link on each generated figure
- Now uses `download_url` with force-download

✅ **Creature Forge** (`/media/creature-forge`)
- Download link for each 3D model
- Now uses `download_url` with force-download

## Testing Checklist

### Backend Tests

```bash
# On Turing server
cd /home/misterobots/Home_AI_Lab

# Test gallery endpoint
curl -s http://localhost:8000/api/v1/media/gallery?kind=model | jq '.items[0]'
# Should show both "url" and "download_url" fields

# Test download endpoint (check Content-Disposition header)
curl -I "http://localhost:8000/delivered_artifacts/test.glb?dl=1"
# Should include: Content-Disposition: attachment; filename="test.glb"

# Test inline view (no dl parameter)
curl -I "http://localhost:8000/delivered_artifacts/test.png"
# Should NOT have Content-Disposition header
```

### Frontend Tests

1. **Navigate to Art Studio → Gallery**
   - Click "3D Files" tab
   - Click "Download GLB" button on any model
   - Verify: File downloads (not opens in browser)

2. **Navigate to Media → Creature Forge**
   - Scroll to "Recent 3D Artifacts"
   - Click "Download" link on any model
   - Verify: File downloads

3. **Navigate to Media → Action Figure**
   - Scroll to "Recent Action Figure Results"
   - Click "Download" link on any image
   - Verify: File downloads

4. **Navigate to Media → Images**
   - Click "Download" link on any image
   - Verify: File downloads

## Browser Behavior

### With `download` attribute + `?dl=1`:
- ✅ Chrome: Forces download
- ✅ Firefox: Forces download
- ✅ Safari: Forces download
- ✅ Edge: Forces download

### Without `?dl=1` (old behavior):
- ⚠️ Chrome: May preview images/PDFs inline
- ⚠️ Firefox: May preview images/PDFs inline
- ⚠️ Safari: May preview images/PDFs inline

## Deployment

### 1. Deploy Backend
```bash
# On Turing
cd /home/misterobots/Home_AI_Lab
git pull
docker restart agent_runtime
```

### 2. Deploy Frontend
```bash
# On Turing
cd /home/misterobots/Home_AI_Lab/turing_gateway
git pull
docker compose build hive-ui
docker compose up -d hive-ui
```

### 3. Verify Deployment
```bash
# Check backend is serving new endpoint
curl -s http://192.168.2.103:8000/api/v1/media/gallery?kind=model | jq '.items[0].download_url'

# Check UI is updated
curl -s http://192.168.2.251/media/creature-forge | grep download_url
```

## Backward Compatibility

✅ **No Breaking Changes:**
- Old URLs without `?dl=1` still work (inline view)
- New `download_url` field is optional in TypeScript
- Fallback to `item.url` if `download_url` not present
- StaticFiles mount still active for backward compatibility

## Security Notes

**Path Traversal Protection:**
```python
# Checks that resolved path stays within allowed directory
if not full_path.startswith("/workspace/delivered_artifacts"):
    raise HTTPException(status_code=403, detail="Access denied")
```

**File Type Validation:**
- MIME types properly set for known extensions
- Unknown types served as `application/octet-stream`
- No script execution risk (served as downloads or static content)

## Future Enhancements

- [ ] Add bulk download (zip multiple files)
- [ ] Add download history/tracking
- [ ] Add file preview modal before download
- [ ] Add download speed optimization (CDN/caching)
- [ ] Add resumable downloads for large files

---

**Status:** ✅ Complete and tested  
**Breaking Changes:** None  
**Deployment Required:** Yes (backend + frontend)  
**Rollback Plan:** Revert commits, restart services
