---
title: "Module: Action Figure"
---

# Action Figure Agent

Designs articulated, posable figures from text descriptions.

## Files

| File | Purpose |
|------|---------|
| `agents/specialized/action_figure_agent.py` | Action figure design pipeline |

## Pipeline

1. **Concept Generation**: FLUX/SDXL generates T-pose concept art
2. **Multi-View Rendering**: Front, side, back orthographic views
3. **Mesh Reconstruction**: 3D mesh from multi-view images
4. **Articulation**: Define joint points (shoulders, elbows, knees, etc.)
5. **Export**: Rigged .glb with articulation metadata

## Joint Schema

```json
{
    "joints": [
        {"name": "neck", "type": "ball", "parent": "torso"},
        {"name": "shoulder_l", "type": "ball", "parent": "torso"},
        {"name": "elbow_l", "type": "hinge", "parent": "shoulder_l"},
        {"name": "hip_l", "type": "ball", "parent": "torso"},
        {"name": "knee_l", "type": "hinge", "parent": "hip_l"}
    ]
}
```

## Related

- [Module: 3D Pipeline](3d-pipeline.md) — underlying 3D systems
- [User Guide: 3D Generation](../user-guide/3d-generation.md#action-figures)


