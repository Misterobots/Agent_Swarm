"""
Workspace search tool for the Librarian / Research agent.

Provides file search and content search within the /workspace directory,
giving the Research agent the ability to find and read project files
when answering questions about the codebase or documentation.
"""

import os
import re
import logging
from typing import List

logger = logging.getLogger("WorkspaceSearch")

WORKSPACE_ROOT = os.getenv("WORKSPACE_ROOT", "/workspace")
MAX_RESULTS = 20
MAX_CONTENT_LENGTH = 4000  # chars per file snippet


def search_files(query: str) -> str:
    """
    Search for files in the workspace by name pattern.
    Returns a list of matching file paths.

    Args:
        query: Glob-like pattern or substring to match against file names.
               Example: "*.py", "router", "README"
    """
    matches = []
    query_lower = query.lower().replace("*", "")

    for root, dirs, files in os.walk(WORKSPACE_ROOT):
        # Skip hidden dirs and common noise
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in (
            "__pycache__", "node_modules", ".git", ".next", "venv"
        )]
        for fname in files:
            if query_lower in fname.lower():
                rel = os.path.relpath(os.path.join(root, fname), WORKSPACE_ROOT)
                matches.append(rel)
                if len(matches) >= MAX_RESULTS:
                    break
        if len(matches) >= MAX_RESULTS:
            break

    if not matches:
        return f"No files matching '{query}' found in workspace."
    return "Matching files:\n" + "\n".join(f"- {m}" for m in matches)


def search_content(pattern: str) -> str:
    """
    Search for a text pattern across all text files in the workspace.
    Returns matching lines with file paths and line numbers.

    Args:
        pattern: Text or regex pattern to search for in file contents.
    """
    results = []
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error:
        # Fall back to literal search
        regex = re.compile(re.escape(pattern), re.IGNORECASE)

    TEXT_EXTENSIONS = {
        ".py", ".js", ".ts", ".tsx", ".md", ".txt", ".json", ".yaml", ".yml",
        ".toml", ".cfg", ".ini", ".sh", ".bat", ".ps1", ".env", ".css", ".html",
    }

    for root, dirs, files in os.walk(WORKSPACE_ROOT):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in (
            "__pycache__", "node_modules", ".git", ".next", "venv",
            "training_output", "migration_backup_20260314_163149",
        )]
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in TEXT_EXTENSIONS:
                continue

            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    for i, line in enumerate(f, 1):
                        if regex.search(line):
                            rel = os.path.relpath(fpath, WORKSPACE_ROOT)
                            results.append(f"{rel}:{i}: {line.rstrip()[:120]}")
                            if len(results) >= MAX_RESULTS:
                                break
            except (PermissionError, OSError):
                continue

            if len(results) >= MAX_RESULTS:
                break
        if len(results) >= MAX_RESULTS:
            break

    if not results:
        return f"No matches for '{pattern}' in workspace files."
    return "Search results:\n" + "\n".join(results)


def read_workspace_file(file_path: str) -> str:
    """
    Read a file from the workspace and return its contents.

    Args:
        file_path: Relative path within the workspace (e.g. 'agents/router.py')
    """
    full_path = os.path.join(WORKSPACE_ROOT, file_path)
    resolved = os.path.realpath(full_path)

    # Security: ensure path stays within workspace
    if not resolved.startswith(os.path.realpath(WORKSPACE_ROOT)):
        return "⛔ Access denied: path is outside workspace."

    if not os.path.isfile(resolved):
        return f"File not found: {file_path}"

    try:
        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        return f"Error reading file: {e}"

    if len(content) > MAX_CONTENT_LENGTH:
        return content[:MAX_CONTENT_LENGTH] + f"\n\n... (truncated, {len(content)} total chars)"
    return content
