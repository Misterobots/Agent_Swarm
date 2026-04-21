---
title: "Module: Forge Agent"
---

# Forge Agent

3D model reconstruction from images and multi-view inputs.

## Files

| File | Purpose |
|------|---------|
| `agents/specialized/forge_agent.py` | 3D reconstruction orchestration |

## Process

1. Takes generated concept images (from Image Agent or user uploads)
2. Generates additional views if needed
3. Runs mesh reconstruction
4. Cleans and optimizes the mesh
5. Exports to .glb, .obj, or .stl

## Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| Output format | .glb (default) | Target mesh format |
| Mesh resolution | Medium | Polygon count target |
| Texture resolution | 1024×1024 | UV texture map size |

## Related

- [Module: 3D Pipeline](3d-pipeline.md) — full pipeline reference
- [Module: Image Agent](image-agent.md) — concept art generation


