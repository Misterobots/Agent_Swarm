"""
qwen_toolparse.py — recover text-format tool calls from local models.

qwen3-coder (and other Qwen3 builds) intermittently ignore Ollama's native
`tool_calls` channel and instead emit the call as *text* in the model's
template markup, e.g.:

    <function=list_directory>
    <parameter=path>
    .
    </parameter>
    </function>

or the Hermes-style JSON variant:

    <tool_call>
    {"name": "write_file", "arguments": {"path": "x.py", "content": "..."}}
    </tool_call>

When `message.tool_calls` is empty we scan the assistant content for these and
recover the calls, returning the content with the markup stripped.  This is the
single biggest reliability fix for the local path; without it the harness
mistakes a tool request for a final answer and stops.
"""

from __future__ import annotations

import json
import re
from typing import Any

# <function=NAME> ... </function>   (DOTALL; name stops at '>' )
_FUNC_RE = re.compile(r"<function\s*=\s*([^>\s]+)\s*>(.*?)</function>", re.DOTALL)
# <parameter=KEY> VALUE </parameter>
_PARAM_RE = re.compile(r"<parameter\s*=\s*([^>\s]+)\s*>(.*?)</parameter>", re.DOTALL)
# <tool_call> {json} </tool_call>   (Hermes-style)
_TOOLCALL_JSON_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
# Stray opening/closing wrapper tags some templates leak.
_STRAY_TAGS_RE = re.compile(r"</?tool_call>", re.IGNORECASE)


def extract_text_tool_calls(content: str) -> tuple[str, list[tuple[str, dict[str, Any]]]]:
    """Return (cleaned_text, [(name, args), ...]).

    `cleaned_text` is `content` with all recovered markup removed.  When nothing
    is found, returns (content, []).
    """
    if not content or "<" not in content:
        return content, []

    calls: list[tuple[str, dict[str, Any]]] = []

    # 1. Hermes-style JSON tool calls.
    for m in _TOOLCALL_JSON_RE.finditer(content):
        try:
            obj = json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            continue
        name = obj.get("name") or obj.get("function") or ""
        args = obj.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (json.JSONDecodeError, ValueError):
                args = {}
        if name:
            calls.append((name, args if isinstance(args, dict) else {}))

    # 2. Pythonic <function=...> blocks.
    for m in _FUNC_RE.finditer(content):
        name = m.group(1).strip()
        body = m.group(2)
        args: dict[str, Any] = {}
        for pm in _PARAM_RE.finditer(body):
            key = pm.group(1).strip()
            val = pm.group(2).strip()
            args[key] = val
        if name:
            calls.append((name, args))

    if not calls:
        return content, []

    # Strip the recovered markup so it isn't shown to the user as prose.
    cleaned = _TOOLCALL_JSON_RE.sub("", content)
    cleaned = _FUNC_RE.sub("", cleaned)
    cleaned = _STRAY_TAGS_RE.sub("", cleaned)
    return cleaned.strip(), calls
