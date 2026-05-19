"""
Bash Parser — Structural command analysis using tree-sitter.

Parses bash/shell commands into an AST and extracts:
  - Individual commands and their arguments
  - Pipe chains
  - Redirections
  - Variable assignments
  - Command substitutions
  - Subshells

Falls back to a regex-based lightweight parser when tree-sitter-bash
is not installed (graceful degradation).

Dependencies (optional):
    pip install tree-sitter tree-sitter-bash
"""

from __future__ import annotations

import logging
import re
import shlex
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("BashParser")

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CommandNode:
    """A single command within a pipeline or compound statement."""
    executable: str
    arguments: List[str] = field(default_factory=list)
    redirections: List[str] = field(default_factory=list)
    is_subshell: bool = False
    is_substitution: bool = False


@dataclass
class ParseResult:
    """Full parse result for a bash command string."""
    raw: str
    commands: List[CommandNode] = field(default_factory=list)
    pipes: int = 0
    has_redirect: bool = False
    has_subshell: bool = False
    has_substitution: bool = False
    variables: List[str] = field(default_factory=list)
    background: bool = False
    chained: bool = False  # ;, &&, ||
    parse_method: str = "fallback"  # "tree-sitter" or "fallback"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw": self.raw,
            "commands": [
                {
                    "executable": c.executable,
                    "arguments": c.arguments,
                    "redirections": c.redirections,
                    "is_subshell": c.is_subshell,
                    "is_substitution": c.is_substitution,
                }
                for c in self.commands
            ],
            "pipes": self.pipes,
            "has_redirect": self.has_redirect,
            "has_subshell": self.has_subshell,
            "has_substitution": self.has_substitution,
            "variables": self.variables,
            "background": self.background,
            "chained": self.chained,
            "parse_method": self.parse_method,
        }

    def __str__(self) -> str:
        cmds = ", ".join(c.executable for c in self.commands)
        flags = []
        if self.pipes:
            flags.append(f"{self.pipes} pipe(s)")
        if self.has_redirect:
            flags.append("redirect")
        if self.has_subshell:
            flags.append("subshell")
        if self.has_substitution:
            flags.append("substitution")
        if self.background:
            flags.append("background")
        if self.chained:
            flags.append("chained")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        return f"Commands: [{cmds}]{flag_str} (via {self.parse_method})"


# ---------------------------------------------------------------------------
# Tree-sitter parser (preferred)
# ---------------------------------------------------------------------------
_TS_AVAILABLE: Optional[bool] = None
_TS_PARSER = None
_TS_LANGUAGE = None


def _init_tree_sitter() -> bool:
    """Attempt to initialize tree-sitter with bash grammar."""
    global _TS_AVAILABLE, _TS_PARSER, _TS_LANGUAGE

    if _TS_AVAILABLE is not None:
        return _TS_AVAILABLE

    try:
        import tree_sitter_bash as tsbash
        from tree_sitter import Language, Parser

        _TS_LANGUAGE = Language(tsbash.language())
        _TS_PARSER = Parser(_TS_LANGUAGE)
        _TS_AVAILABLE = True
        logger.info("[BashParser] tree-sitter-bash loaded successfully")
    except ImportError:
        _TS_AVAILABLE = False
        logger.info("[BashParser] tree-sitter-bash not available, using fallback parser")
    except Exception as e:
        _TS_AVAILABLE = False
        logger.warning(f"[BashParser] tree-sitter init failed: {e}")

    return _TS_AVAILABLE


def _parse_tree_sitter(command: str) -> ParseResult:
    """Parse using tree-sitter-bash for accurate AST extraction."""
    tree = _TS_PARSER.parse(bytes(command, "utf-8"))
    root = tree.root_node

    result = ParseResult(raw=command, parse_method="tree-sitter")

    def _extract_text(node) -> str:
        return command[node.start_byte:node.end_byte]

    def _walk(node):
        if node.type == "command":
            cmd_node = CommandNode(executable="")
            for child in node.children:
                if child.type == "command_name":
                    cmd_node.executable = _extract_text(child)
                elif child.type in ("word", "string", "raw_string", "concatenation", "simple_expansion"):
                    cmd_node.arguments.append(_extract_text(child))
            if cmd_node.executable:
                result.commands.append(cmd_node)

        elif node.type == "pipeline":
            result.pipes += max(0, len([c for c in node.children if c.type == "|"]))

        elif node.type == "redirected_statement":
            result.has_redirect = True
            for child in node.children:
                if child.type in ("file_redirect", "heredoc_redirect"):
                    redir_text = _extract_text(child)
                    if result.commands:
                        result.commands[-1].redirections.append(redir_text)

        elif node.type == "subshell":
            result.has_subshell = True

        elif node.type == "command_substitution":
            result.has_substitution = True

        elif node.type == "variable_assignment":
            result.variables.append(_extract_text(node))

        elif node.type == "list":
            # ; && || 
            result.chained = True

        for child in node.children:
            _walk(child)

    _walk(root)

    # Check for background (&)
    if command.rstrip().endswith("&") and not command.rstrip().endswith("&&"):
        result.background = True

    return result


# ---------------------------------------------------------------------------
# Fallback regex-based parser
# ---------------------------------------------------------------------------

def _parse_fallback(command: str) -> ParseResult:
    """Lightweight regex-based parser when tree-sitter is not available."""
    result = ParseResult(raw=command, parse_method="fallback")

    # Strip trailing comments
    clean = re.sub(r"#.*$", "", command).strip()

    # Detect background
    if clean.endswith("&") and not clean.endswith("&&"):
        result.background = True
        clean = clean[:-1].strip()

    # Detect chaining
    if re.search(r"[;&]|&&|\|\|", clean):
        result.chained = True

    # Split on pipes (outside quotes)
    segments = _split_pipes(clean)
    result.pipes = max(0, len(segments) - 1)

    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue

        # Detect redirections
        redir_match = re.findall(r"([012]?>>?&?\s*\S+)", seg)
        if redir_match:
            result.has_redirect = True

        # Remove redirections for command parsing
        cleaned = re.sub(r"[012]?>>?&?\s*\S+", "", seg).strip()

        # Detect subshell
        if cleaned.startswith("(") and cleaned.endswith(")"):
            result.has_subshell = True
            node = CommandNode(executable="(subshell)", is_subshell=True)
            result.commands.append(node)
            continue

        # Detect command substitution
        if "$(" in cleaned or "`" in cleaned:
            result.has_substitution = True

        # Detect variable assignment
        var_match = re.match(r"^(\w+=\S*)\s*(.*)", cleaned)
        if var_match:
            result.variables.append(var_match.group(1))
            cleaned = var_match.group(2).strip()
            if not cleaned:
                continue

        # Parse command + arguments
        try:
            parts = shlex.split(cleaned)
        except ValueError:
            parts = cleaned.split()

        if parts:
            node = CommandNode(
                executable=parts[0],
                arguments=parts[1:],
                redirections=redir_match if redir_match else [],
            )
            result.commands.append(node)

    return result


def _split_pipes(command: str) -> List[str]:
    """Split a command by pipe characters, respecting quotes and subshells."""
    segments = []
    current = []
    depth = 0
    in_single = False
    in_double = False
    i = 0

    while i < len(command):
        ch = command[i]

        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth = max(0, depth - 1)
            elif ch == "|" and depth == 0:
                # Check it's not || 
                if i + 1 < len(command) and command[i + 1] == "|":
                    current.append(ch)
                    i += 1
                    current.append(command[i])
                    i += 1
                    continue
                else:
                    segments.append("".join(current))
                    current = []
                    i += 1
                    continue

        current.append(ch)
        i += 1

    if current:
        segments.append("".join(current))

    return segments


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_bash(command: str) -> ParseResult:
    """Parse a bash command string into structured components.

    Uses tree-sitter-bash if available, otherwise falls back to regex parsing.
    """
    command = command.strip()
    if not command:
        return ParseResult(raw=command, parse_method="fallback")

    if _init_tree_sitter():
        try:
            return _parse_tree_sitter(command)
        except Exception as e:
            logger.warning(f"[BashParser] tree-sitter parse failed, using fallback: {e}")

    return _parse_fallback(command)


def get_executables(command: str) -> List[str]:
    """Quick extraction of just the executable names from a command."""
    result = parse_bash(command)
    return [c.executable for c in result.commands if c.executable]
