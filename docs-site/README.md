# Agent Swarm Docs Site

Local development and deployment for the Agent Swarm documentation library.

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Serve with live reload (http://localhost:8000)
mkdocs serve

# Build static site
mkdocs build --strict
```

## Docker Build

```bash
docker build -t agent-swarm-docs .
docker run -p 8080:80 agent-swarm-docs
```

## Deploy to GitHub Pages

Pushes to `docs-site/**` on `main` automatically deploy via GitHub Actions.

Manual deploy:

```bash
mkdocs gh-deploy --force
```
