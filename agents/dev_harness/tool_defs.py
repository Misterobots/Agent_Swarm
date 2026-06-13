"""
tool_defs.py — canonical DEV_TOOL_DEFINITIONS list.

Shared by both main.py (HiveCode dev harness) and
coordination/devharness_worker.py (Swarm workers on DevHarness).
Keeping it here avoids importing main.py (FastAPI app) from library code.
"""

DEV_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the dev sandbox workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to /workspace (e.g. 'src/app.py')",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or overwrite a file in the dev sandbox workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to /workspace",
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete new content for the file",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List the contents of a directory in the dev sandbox workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path relative to /workspace (default: '.')",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Execute a shell command in the dev sandbox. "
                "The sandbox has Python 3, Node.js 20, git, and common build tools. "
                "Use this to run tests, install packages, build projects, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Bash command to execute",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory relative to /workspace (optional)",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Make a precise edit to an EXISTING file by replacing an exact string. "
                "Prefer this over write_file for changes to existing files. old_string must "
                "match exactly (including whitespace/indentation) and be unique unless "
                "replace_all is true. Returns a unified diff of the change."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to /workspace"},
                    "old_string": {"type": "string", "description": "Exact text to replace (unique unless replace_all)"},
                    "new_string": {"type": "string", "description": "Replacement text"},
                    "replace_all": {"type": "boolean", "description": "Replace all occurrences (default false)"},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob",
            "description": "Find files by glob pattern (e.g. '**/*.py', 'src/*.ts'). Returns matching paths; respects .gitignore.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern, e.g. '**/*.py'"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search file contents for a regex (ripgrep). Returns matching lines as file:line: text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "path": {"type": "string", "description": "File or dir to search (default: whole workspace)"},
                    "ignore_case": {"type": "boolean", "description": "Case-insensitive (default false)"},
                    "glob": {"type": "string", "description": "Only search files matching this glob, e.g. '*.py'"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git",
            "description": (
                "Run a git command in the workspace. command is one of: status, diff, log, add, "
                "commit, branch, show, init. Supply 'message' for commit; optionally 'paths' for add/diff."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "status|diff|log|add|commit|branch|show|init"},
                    "message": {"type": "string", "description": "Commit message (required for commit)"},
                    "paths": {"type": "array", "items": {"type": "string"}, "description": "File paths for add/diff"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "TodoWrite",
            "description": (
                "Record or update your task list for the current request. Use it to plan multi-step "
                "work and to mark steps in_progress/completed as you go. Pass the FULL list each time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "todos": {
                        "type": "array",
                        "description": "The complete, current todo list",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {"type": "string", "description": "What the step does"},
                                "status": {
                                    "type": "string",
                                    "enum": ["pending", "in_progress", "completed"],
                                    "description": "Step status",
                                },
                                "activeForm": {"type": "string", "description": "Present-continuous label shown while in progress"},
                            },
                            "required": ["content", "status"],
                        },
                    },
                },
                "required": ["todos"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "Task",
            "description": (
                "Delegate a focused, self-contained sub-task to an autonomous subagent that has the "
                "same sandbox tools. Use for well-scoped work (e.g. 'investigate and summarize how X "
                "works', 'implement and test module Y'). The subagent runs to completion and returns a "
                "summary; it cannot spawn further subagents. Spawning requires user approval."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "Short label for the sub-task"},
                    "prompt": {"type": "string", "description": "The full, self-contained instruction for the subagent"},
                    "subagent_type": {"type": "string", "description": "Kind of subagent, e.g. 'general', 'researcher', 'coder'"},
                },
                "required": ["description", "prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web; returns top results (title, url, snippet). Use to look up docs, errors, or library/API usage.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Search query"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch and read a web page as text (e.g. a documentation page). Provide the full URL.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "Full URL to fetch"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kb_search",
            "description": (
                "Search the Memex knowledge base (PgVector) for relevant prior art, architectural "
                "decisions, and reusable patterns. Use before implementing a feature to see if the "
                "KB has existing context on the problem."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural-language search query"},
                    "limit": {"type": "integer", "description": "Max results to return (default 5, max 8)"},
                },
                "required": ["query"],
            },
        },
    },
]
