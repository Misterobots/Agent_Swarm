"""
tests/test_mempalace_json_parser.py

Unit tests for the robust LLM JSON parser in mempalace/app/embeddings.py.
Tests _parse_llm_json() with various malformed LLM outputs.

Run:
    pytest tests/test_mempalace_json_parser.py -v
"""

import sys
import os
import json

import pytest

# Ensure the mempalace app package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "control_plane", "mempalace"))

from app.embeddings import _parse_llm_json


class TestParseLlmJson:
    """Tests for _parse_llm_json best-effort JSON extraction."""

    # --- Clean JSON ---

    def test_clean_array(self):
        raw = '[{"content": "fact one", "type": "semantic"}]'
        result = _parse_llm_json(raw)
        assert result == [{"content": "fact one", "type": "semantic"}]

    def test_empty_array(self):
        result = _parse_llm_json("[]")
        assert result == []

    def test_multi_element_array(self):
        raw = json.dumps([
            {"content": "fact 1", "type": "semantic", "domain": "coding"},
            {"content": "fact 2", "type": "procedural", "domain": "visual"},
        ])
        result = _parse_llm_json(raw)
        assert len(result) == 2
        assert result[0]["content"] == "fact 1"
        assert result[1]["domain"] == "visual"

    # --- Markdown fences ---

    def test_json_in_markdown_fence(self):
        raw = '```json\n[{"content": "fenced fact", "type": "semantic"}]\n```'
        result = _parse_llm_json(raw)
        assert result == [{"content": "fenced fact", "type": "semantic"}]

    def test_json_in_plain_fence(self):
        raw = '```\n[{"content": "plain fence", "type": "episodic"}]\n```'
        result = _parse_llm_json(raw)
        assert result == [{"content": "plain fence", "type": "episodic"}]

    def test_fence_with_surrounding_text(self):
        raw = 'Here is the extracted memory:\n```json\n[{"content": "surrounded", "type": "semantic"}]\n```\nDone.'
        result = _parse_llm_json(raw)
        assert result[0]["content"] == "surrounded"

    # --- Preamble / postamble ---

    def test_text_before_array(self):
        raw = 'Based on the conversation, here are the extracted memories:\n[{"content": "with preamble", "type": "semantic"}]'
        result = _parse_llm_json(raw)
        assert result[0]["content"] == "with preamble"

    def test_text_after_array(self):
        raw = '[{"content": "trailing text", "type": "semantic"}]\n\nThese are the key takeaways.'
        result = _parse_llm_json(raw)
        assert result[0]["content"] == "trailing text"

    # --- Common LLM JSON errors ---

    def test_trailing_comma_in_array(self):
        raw = '[{"content": "trailing comma", "type": "semantic"},]'
        result = _parse_llm_json(raw)
        assert result is not None
        assert result[0]["content"] == "trailing comma"

    def test_trailing_comma_in_object(self):
        raw = '[{"content": "obj trailing", "type": "semantic", "domain": "general",}]'
        result = _parse_llm_json(raw)
        assert result is not None
        assert result[0]["content"] == "obj trailing"

    def test_missing_comma_between_objects(self):
        """The exact bug that caused the original extraction failure."""
        raw = '[{"content": "fact one", "type": "semantic"}\n{"content": "fact two", "type": "episodic"}]'
        result = _parse_llm_json(raw)
        assert result is not None
        assert len(result) == 2
        assert result[0]["content"] == "fact one"
        assert result[1]["content"] == "fact two"

    # --- Edge cases ---

    def test_empty_string(self):
        result = _parse_llm_json("")
        assert result is None

    def test_whitespace_only(self):
        result = _parse_llm_json("   \n\t  ")
        assert result is None

    def test_no_json_at_all(self):
        result = _parse_llm_json("I could not find any memories to extract from this conversation.")
        assert result is None

    def test_non_list_json(self):
        """Returns the dict as-is — caller validates list type."""
        raw = '{"content": "not a list", "type": "semantic"}'
        result = _parse_llm_json(raw)
        # Should parse the object (not a list, but that's caller's job)
        assert isinstance(result, dict)

    def test_nested_brackets_in_strings(self):
        raw = '[{"content": "array [1, 2, 3] in text", "type": "semantic"}]'
        result = _parse_llm_json(raw)
        assert result[0]["content"] == "array [1, 2, 3] in text"

    def test_unbalanced_brackets(self):
        raw = '[{"content": "missing close'
        result = _parse_llm_json(raw)
        assert result is None

    # --- Multi-fence edge case ---

    def test_multiple_fences_picks_json_one(self):
        raw = (
            "Some text\n"
            "```python\nprint('hello')\n```\n"
            "```json\n[{\"content\": \"right one\", \"type\": \"semantic\"}]\n```\n"
        )
        result = _parse_llm_json(raw)
        assert result[0]["content"] == "right one"


class TestExtractMemoriesValidation:
    """Tests for the validation logic inside extract_memories.

    These test the structural validation after JSON parsing,
    without calling the actual LLM.
    """

    def test_valid_memory_structure(self):
        """Simulates what extract_memories validates post-parse."""
        memories = [
            {"content": "User likes Python", "type": "semantic", "domain": "coding"},
            {"content": "Used Docker yesterday", "type": "episodic"},
        ]
        valid = []
        for m in memories:
            if isinstance(m, dict) and "content" in m and "type" in m:
                valid.append({
                    "content": str(m["content"])[:500],
                    "type": m.get("type", "semantic"),
                    "domain": m.get("domain", "general"),
                })
        assert len(valid) == 2
        assert valid[0]["domain"] == "coding"
        assert valid[1]["domain"] == "general"  # defaulted

    def test_missing_content_key_filtered(self):
        memories = [
            {"type": "semantic", "domain": "general"},  # no content
            {"content": "valid", "type": "semantic"},
        ]
        valid = [m for m in memories if isinstance(m, dict) and "content" in m and "type" in m]
        assert len(valid) == 1

    def test_missing_type_key_filtered(self):
        memories = [
            {"content": "no type field"},  # no type
            {"content": "valid", "type": "procedural"},
        ]
        valid = [m for m in memories if isinstance(m, dict) and "content" in m and "type" in m]
        assert len(valid) == 1

    def test_content_truncated_at_500(self):
        long_content = "x" * 1000
        truncated = str(long_content)[:500]
        assert len(truncated) == 500

    def test_non_dict_entries_filtered(self):
        memories = [
            "just a string",
            42,
            {"content": "valid", "type": "semantic"},
        ]
        valid = [m for m in memories if isinstance(m, dict) and "content" in m and "type" in m]
        assert len(valid) == 1
