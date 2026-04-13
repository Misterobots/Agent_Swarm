"""
tests/test_bash_parser.py

Unit tests for the Bash Parser (Tree-Sitter + fallback).

Run:
    pytest tests/test_bash_parser.py -v
"""

import sys
import os

import pytest

# Ensure agents dir is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))


from tools.bash_parser import parse_bash, get_executables, ParseResult


# ═══════════════════════════════════════════════════════════════════════════
# Simple Commands
# ═══════════════════════════════════════════════════════════════════════════

class TestSimpleCommands:
    def test_single_command(self):
        result = parse_bash("ls -la")
        assert len(result.commands) == 1
        assert result.commands[0].executable == "ls"
        assert "-la" in result.commands[0].arguments

    def test_command_with_path_arg(self):
        result = parse_bash("cat /etc/hosts")
        assert result.commands[0].executable == "cat"
        assert "/etc/hosts" in result.commands[0].arguments

    def test_empty_command(self):
        result = parse_bash("")
        assert len(result.commands) == 0

    def test_whitespace_only(self):
        result = parse_bash("   ")
        assert len(result.commands) == 0

    def test_get_executables_helper(self):
        execs = get_executables("ls -la | grep test | wc -l")
        assert "ls" in execs
        assert "grep" in execs
        assert "wc" in execs


# ═══════════════════════════════════════════════════════════════════════════
# Pipe Chains
# ═══════════════════════════════════════════════════════════════════════════

class TestPipeChains:
    def test_single_pipe(self):
        result = parse_bash("cat file.txt | grep error")
        assert result.pipes >= 1
        execs = [c.executable for c in result.commands]
        assert "cat" in execs
        assert "grep" in execs

    def test_multi_pipe(self):
        result = parse_bash("ps aux | grep python | awk '{print $2}' | head -5")
        assert result.pipes >= 3
        assert len(result.commands) >= 4

    def test_no_pipe(self):
        result = parse_bash("echo hello")
        assert result.pipes == 0


# ═══════════════════════════════════════════════════════════════════════════
# Redirections
# ═══════════════════════════════════════════════════════════════════════════

class TestRedirections:
    def test_output_redirect(self):
        result = parse_bash("echo hello > output.txt")
        assert result.has_redirect is True

    def test_append_redirect(self):
        result = parse_bash("echo hello >> output.txt")
        assert result.has_redirect is True

    def test_no_redirect(self):
        result = parse_bash("echo hello")
        assert result.has_redirect is False


# ═══════════════════════════════════════════════════════════════════════════
# Subshell and Substitution Detection
# ═══════════════════════════════════════════════════════════════════════════

class TestSubshellAndSubstitution:
    def test_command_substitution_dollar(self):
        result = parse_bash("echo $(whoami)")
        assert result.has_substitution is True

    def test_command_substitution_backtick(self):
        result = parse_bash("echo `date`")
        assert result.has_substitution is True

    def test_no_substitution(self):
        result = parse_bash("echo hello world")
        assert result.has_substitution is False


# ═══════════════════════════════════════════════════════════════════════════
# Variable Assignments
# ═══════════════════════════════════════════════════════════════════════════

class TestVariableAssignment:
    def test_simple_assignment(self):
        result = parse_bash("FOO=bar echo $FOO")
        assert len(result.variables) >= 1
        assert any("FOO" in v for v in result.variables)


# ═══════════════════════════════════════════════════════════════════════════
# Background & Chaining
# ═══════════════════════════════════════════════════════════════════════════

class TestBackgroundAndChaining:
    def test_background_process(self):
        result = parse_bash("sleep 100 &")
        assert result.background is True

    def test_not_background(self):
        result = parse_bash("echo hello")
        assert result.background is False

    def test_double_ampersand_not_background(self):
        result = parse_bash("make && make install")
        assert result.background is False

    def test_chained_commands(self):
        result = parse_bash("cd /tmp && ls -la")
        assert result.chained is True


# ═══════════════════════════════════════════════════════════════════════════
# Serialization
# ═══════════════════════════════════════════════════════════════════════════

class TestSerialization:
    def test_to_dict(self):
        result = parse_bash("ls -la | grep test")
        d = result.to_dict()
        assert d["raw"] == "ls -la | grep test"
        assert d["pipes"] >= 1
        assert isinstance(d["commands"], list)
        assert d["parse_method"] in ("tree-sitter", "fallback")

    def test_str_representation(self):
        result = parse_bash("echo hello")
        s = str(result)
        assert "echo" in s
        assert "via" in s

    def test_parse_method_reported(self):
        result = parse_bash("ls")
        assert result.parse_method in ("tree-sitter", "fallback")
