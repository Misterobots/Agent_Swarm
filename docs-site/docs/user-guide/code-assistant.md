---
title: Code Assistant
---

# Code Assistant

Write, debug, test, and execute code with inference-time verification and sandboxed execution.

## How to Access

- **Chat**: Any coding request is automatically routed to the `CODE` intent
- **Dev Mode**: Set `dev_mode: true` to enable file operations and terminal tools

## Quick Example

> *"Write a Python function to find the longest common subsequence of two strings"*

The MarsRL loop ensures the generated code:

1. Parses correctly (AST check)
2. Is coherent and non-repetitive
3. Passes safety validation

## Detailed Usage

### What the Code Assistant Can Do

| Capability | Description |
|------------|-------------|
| **Generate code** | Functions, classes, scripts in any language |
| **Debug** | Analyze errors, suggest fixes, trace issues |
| **Explain** | Walk through code logic, document functions |
| **Refactor** | Improve structure, naming, patterns |
| **Test** | Write unit tests, integration tests |
| **Execute** | Run code in sandboxed environments (Dev Mode) |
| **Git operations** | Clone, commit, push, branch management |

### Dev Mode Tools

When `dev_mode: true`, these tools become available:

| Tool | Function | Description |
|------|----------|-------------|
| `read_file` | `read_file(path)` | Read file contents |
| `write_file` | `write_file(path, content)` | Create or overwrite a file |
| `list_directory` | `list_directory(path)` | List directory contents |
| `run_command` | `run_command(cmd)` | Execute a shell command |
| `web_search` | `web_search(query)` | Search the web |
| `fetch_page` | `fetch_page(url)` | Retrieve and parse a webpage |

### Sandboxed Execution (OpenHands)

For full code execution with an isolated environment, the system can delegate to OpenHands — a sandboxed VS Code instance with Docker-in-Docker support.

Access OpenHands directly at `http://{{ gateway_node_ip }}:3002`.

### MarsRL Quality Loop for Code

The verifier applies code-specific checks:

1. **AST Parse**: Validates Python syntax (score penalty: −0.40 if invalid)
2. **Coherence**: Ensures output isn't empty or repetitive (penalty: −0.25)
3. **Safety**: llama-guard-3 content check (hard block if unsafe)

Pass threshold: score ≥ 0.60. If verification fails, the Corrector agent rewrites the code (up to 2 iterations).

## Tips & Common Patterns

!!! tip "Be Explicit About Language"
    Specify the language in your prompt. *"Write a Rust HTTP server"* routes more accurately than *"Write a web server"*.

!!! tip "Multi-File Projects"
    For complex projects, use the `COORDINATE` intent by describing the full scope: *"Build a REST API with FastAPI, a database model, and unit tests"*. The Coordinator decomposes it into subtasks.

!!! tip "Safety Limits"
    The security agent blocks dangerous commands (e.g., `rm -rf /`, `curl | bash`). This is intentional. Use the governance system to request elevated permissions.

## Related

- [Architecture: MarsRL](../architecture/marsrl.md) — quality verification loop
- [Module: Router](../modules/router.md) — intent classification
- [Module: Coordinator](../modules/coordinator.md) — multi-worker orchestration
- [Developer Guide: Adding Tools](../developer-guide/adding-tools.md) — extend the tool set
- [Troubleshooting: Common Errors](../troubleshooting/agent-runtime.md)
