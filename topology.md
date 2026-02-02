# System Architecture: Home AI Lab v2

## 🗺️ High-Level Topology

This system is a **Hybrid Swarm**, split into a **Logic Plane** (Docker Containers) and a **Creative Plane** (Local GPU Host).

```mermaid
graph TD
    %% Styling
    classDef user fill:#fff,stroke:#333,stroke-width:2px;
    classDef logic fill:#e1f5d4,stroke:#333,stroke-width:1px;
    classDef factory fill:#d4e1f5,stroke:#333,stroke-width:1px;

    %% 1. USER
    User((🤵 User)):::user

    %% 2. LOGIC PLANE (Docker)
    subgraph Logic_Plane ["⚡ LOGIC PLANE (Docker)"]
        direction TB
        AgentUI[🖥️ Agent UI]:::logic
        Router{🧠 Router}:::logic
        ArtDirector[🎨 Art Director]:::logic
        Studio[🖌️ Creative Studio]:::logic
        
        %% Internal Flow
        User --> AgentUI --> Router
        Router -->|Image Request| ArtDirector
        ArtDirector -->|Refined Prompt| Studio
    end

    %% 3. CREATIVE PLANE (Local Host)
    subgraph Creative_Plane ["🏭 CREATIVE PLANE (Local Host)"]
        direction TB
        ComfyUI[⚙️ ComfyUI Engine]:::factory
        Validator[👁️ Validation Server]:::factory
        GPU((🚀 RTX 5060 Ti)):::factory

        %% Factory Flow
        Studio -->|1. Generate| ComfyUI
        ComfyUI --> GPU
        Studio -->|2. Verify via VLM| Validator
        Validator -.->|Pass/Fail| Studio
    end
```

---

## 🔌 Service Map

| Service | Port | Function |
| :--- | :--- | :--- |
| **Agent UI** | `8501` | 💬 Chat Interface |
| **ComfyUI** | `8188` | 🎨 Image Engine |
| **Ollama** | `11434`| 🧠 AI Models |
| **Grafana** | `80` | 📊 Metrics |
| **Validation**| `5000` | 👁️ Visual Checks |

---

## 🚀 Unified Controls

Use `launch_swarm.bat` to manage the entire system.

*   **startup**: Launches Docker + ComfyUI together.
*   **shutdown**: Press **`Q`** in the launcher window to clean kill all processes.
