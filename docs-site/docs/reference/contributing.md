---
title: Contributing
---

# Contributing

Thank you for your interest in contributing to Agent Swarm.

## Getting Started

1. Fork the repository
2. Clone your fork
3. Set up a [local development environment](../developer-guide/local-dev.md)
4. Create a feature branch: `git checkout -b feature/my-feature`

## Development Workflow

1. Make your changes
2. Write or update tests
3. Run tests: `pytest`
4. Commit with a clear message: `git commit -m "Add: my new feature"`
5. Push to your fork: `git push origin feature/my-feature`
6. Open a Pull Request

## Code Standards

- Python: follow PEP 8
- Use type hints for function signatures
- Add docstrings for public functions and classes
- Log errors with contextual information

## Pull Request Guidelines

- One feature/fix per PR
- Include a clear description of what and why
- Reference related issues
- Ensure all tests pass
- Keep PRs focused and reasonably sized

## Areas for Contribution

- **New Agents** — see [Adding Agents](../developer-guide/adding-agents.md)
- **New Tools** — see [Adding Tools](../developer-guide/adding-tools.md)
- **Documentation** — fix typos, improve clarity, add examples
- **Bug Fixes** — check open issues
- **Tests** — improve coverage

## Reporting Issues

Open a GitHub issue with:

- Clear description of the problem
- Steps to reproduce
- Expected vs. actual behavior
- Logs or error messages
- Environment details (OS, GPU, Docker version)

## Documentation Contributions

Documentation lives in `docs-site/docs/`. To preview:

```bash
cd docs-site
pip install -r requirements.txt
mkdocs serve
```

Then open `http://localhost:8000`.
