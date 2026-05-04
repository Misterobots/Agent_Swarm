---
title: Home
---

# Memex Documentation

**A self-hosted, distributed multi-agent AI system for home automation, coding, creative media, and voice interaction.**

Version {{ version }} · {{ phase }} · All inference runs on-premises  no external AI services.

---

## What is Memex?

Memex (also called **Memex** or **Home AI Lab**) is a production multi-agent system running across three physical nodes on a local network. It provides:

- **Intelligent chat and coding** with inference-time quality verification (MarsRL)
- **Image, 3D, and action figure generation** via ComfyUI pipelines
- **Voice interaction** with BMO character synthesis and TTS
- **Smart home control** through Home Assistant integration
- **Zero-trust security** using SPIFFE/SPIRE workload identity and JWT-ACE tokens

```mermaid
graph TB
    subgraph Gateway["Gateway Node · Turing<br/>{{ turing_ip }}"]
        Traefik[Traefik Reverse Proxy]
        hollerith[hollerith Dashboards]
        jacquard[jacquard Metrics]
        knuth[knuth Logs]
    end

    subgraph Execution["Execution Node · Lovelace<br/>{{ lovelace_ip }}"]
        Runtime[Agent Runtime · FastAPI]
        Ollama[Ollama · LLM Inference]
        ComfyUI[ComfyUI · Image Gen]
        Voice[Voice Engine · TTS]
    end

    subgraph Control["Control Node<br/>{{ hopper_ip }}"]
        SPIRE[SPIRE Server]
        Langfuse[Langfuse · Tracing]
        PostgreSQL[(PostgreSQL)]
        MemPalace[MemPalace · Memory]
    end

    Traefik --> Runtime
    Runtime --> Ollama
    Runtime --> ComfyUI
    Runtime --> Voice
    Runtime --> SPIRE
    Runtime --> Langfuse
    Runtime --> PostgreSQL
    Runtime --> MemPalace
```

---

## Choose Your Path

<div class="grid cards" markdown>

-   :material-account:{ .lg .middle } **I'm a User**

    ---

    Learn how to use Memex  chat, generate images, control devices, and more.

    [:octicons-arrow-right-24: User Quickstart](getting-started/quickstart-user.md)

-   :material-server:{ .lg .middle } **I'm an Admin**

    ---

    Deploy, configure, and operate the 3-node cluster.

    [:octicons-arrow-right-24: Admin Quickstart](getting-started/quickstart-admin.md)

-   :material-code-braces:{ .lg .middle } **I'm a Developer**

    ---

    Extend the system  add agents, tools, skills, or modify the runtime.

    [:octicons-arrow-right-24: Developer Quickstart](getting-started/quickstart-developer.md)

-   :material-book-open-variant:{ .lg .middle } **Browse All Docs**

    ---

    Explore the full documentation library.

    [:octicons-arrow-right-24: Getting Started](getting-started/overview.md)

</div>

---

## Quick Links

| Section | Description |
|---------|-------------|
| [User Guide](user-guide/index.md) | Feature-by-feature usage guides |
| [Architecture](architecture/index.md) | System design, data flows, MarsRL, security |
| [Admin Guide](admin-guide/index.md) | Deployment, operations, configuration |
| [Developer Guide](developer-guide/index.md) | Local setup, API reference, extending the system |
| [Modules](modules/index.md) | In-depth documentation of every module and service |
| [Procedures](procedures/index.md) | Step-by-step operational runbooks |
| [Tutorials](tutorials/index.md) | Guided walkthroughs with examples |
| [FAQ](faq/index.md) | Frequently asked questions |
| [Troubleshooting](troubleshooting/index.md) | Symptom-based problem resolution |
| [Reference](admin-guide/port-map.md) | Port map, env vars, glossary |


