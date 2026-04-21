---
title: "Tool: AST Tool"
---

# AST Tool

Python Abstract Syntax Tree analysis.

## Functions

| Function | Description |
|----------|-------------|
| `parse_python(code)` | Parse code and return AST |
| `validate_syntax(code)` | Check for syntax errors |
| `extract_functions(code)` | List function definitions |

## Used By

- **Verifier**: Layer 1 AST check in MarsRL
- **Code Agent**: Code analysis and refactoring

## Allowed Intents

`CODE`


