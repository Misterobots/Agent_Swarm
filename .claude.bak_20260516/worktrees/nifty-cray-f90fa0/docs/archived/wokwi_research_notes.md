# Research Notes: Wokwi Simulator Integration

**Date**: 2026-02-02
**Researcher**: Antigravity

## 1. Feasibility Analysis

- **Web Embedding**: Verified. Wokwi projects can be embedded via `<iframe>` using the URL pattern `https://wokwi.com/projects/{id}?embed=1`.
- **Dynamic Firmware**: High Complexity. Sending compiled hex files from a local agent to the Wokwi Web App is non-trivial without a paid API or custom-hosted instance.
- **Local Simulation**:
  - **Wokwi for VS Code**: Excellent local support. Agents can write `diagram.json` + `main.cpp`, and the user can click "Start Simulation" in VS Code.
  - **CI/CD**: Wokwi CLI tool exists (beta) to run sims headless.

## 2. Impact Assessment

- **Safety**: **CRITICAL POSITIVE**. Agents can "burn to silicon" in Wokwi first. If the Wokwi sim crashes or the LED doesn't blink, we abort the physical burn.
- **Development Speed**: Fast iteration loop (compile -> sim -> verify) without hardware setup.

## 3. Recommended Approach: "Hybrid Workflow"

1.  **Agent Action**: Agent writes `firmware.cpp` and `diagram.json` to a local `simulations/` directory.
2.  **UI Visualization**: Streamlit displays the link: `file:///simulations/project_folder`.
3.  **User Action for V1**: User opens folder in VS Code and runs Wokwi extension.
4.  **Future (V2)**: We integrate a Wokwi-compatible web viewer into Streamlit (requires more JS work).

## 4. Proposed Tooling

- `tools/wokwi_ops.py`:
  - `create_project(name, board_type="esp32")`
  - `add_part(part_id, x, y)`
  - `connect_wires(source, target)`
