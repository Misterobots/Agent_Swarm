# Swarm Network Topology: Port Map

This document lists all reserved ports for the Home AI Lab services to prevent conflicts.

## 🟢 Public / UI Ports
| Service | Port | Access URL | Description |
| :--- | :--- | :--- | :--- |
| **Agent UI** | `8501` | [http://localhost:8501](http://localhost:8501) | Main Streamlit Interface (Chat & Control) |
| **Mission Control** | `80` | [http://localhost:80](http://localhost:80) | Grafana Dashboards (redirects internally to 3000) |
| **Creature Forge** | `3005` | [http://localhost:3005](http://localhost:3005) | Specialized 3D Model Generator UI |
| **ComfyUI** | `8188` | [http://localhost:8188](http://localhost:8188) | Node-based Workflow Editor |

## 🟠 Infrastructure / API Ports
| Service | Port | Description |
| :--- | :--- | :--- |
| **Agent Runtime** | `8000` | FastAPI Backend (POST /api/v1/task) |
| **Ollama** | `11434` | LLM Inference API |
| **OpenHands** | `3000` | AI Software Engineer Sandbox (Conflict resolved: Forge moved to 3005) |
| **PostgreSQL** | `5432` | Long-Term Memory Database (Control Plane) |
| **Redis** | `6379` | Task Queue & Throttling Buffer |

## 🟣 Monitoring Ports
| Service | Port | Description |
| :--- | :--- | :--- |
| **Prometheus** | `9090` | Metals Scraper & Time Series DB |
| **Loki** | `3100` | Log Aggregation System |
| **cAdvisor** | `8080` | Container Resource Usage Metrics |
| **UI Metrics** | `8001` | Streamlit-specific Runtime Metrics |

## 🔧 Deployment Notes
- **Creature Forge**: Configured in `vite.config.ts` to use `3005` to avoid colliding with OpenHands (`3000`).
- **Grafana**: Maps Host `80` -> Container `3000`.
- **Spire**: Runs on `8081` (Control Plane).
