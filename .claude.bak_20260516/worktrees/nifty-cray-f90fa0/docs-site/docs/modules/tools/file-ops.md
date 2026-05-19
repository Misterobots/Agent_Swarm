---
title: "Tool: File Operations"
---

# File Operations Tool

Read, write, and list files in the workspace.

## Functions

| Function | Description |
|----------|-------------|
| `read_file(path)` | Read file contents |
| `write_file(path, content)` | Write/overwrite a file |
| `list_files(path)` | List directory contents |
| `file_exists(path)` | Check file existence |

## Security

- Only accessible with `file_ops` in JWT-ACE token
- Restricted to `/workspace/` directory tree
- Cannot access system files or other containers
- Write operations are logged for audit

## Allowed Intents

`CODE`, `DEVOPS`, `DATA`, `COORDINATE`


