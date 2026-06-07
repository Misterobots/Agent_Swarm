"""Unit tests for entity graph functions — no DB, no network.

Tests build_entity_graph, render_entity_html, and the updated analyze()
that auto-detects entity vs. similarity mode.
"""
from __future__ import annotations

import json
import pytest
import networkx as nx

from app.graph import (
    build_entity_graph,
    detect_communities,
    analyze,
    to_node_link_json,
    render_entity_html,
)


# ── Helpers ───────────────────────────────────────────────────────────────


def _make_entities(n: int) -> list[dict]:
    types = ["technology", "project", "person", "concept", "decision", "tool"]
    return [
        {
            "id": f"ent-{i}",
            "label": f"Entity {i}",
            "entity_type": types[i % len(types)],
            "memory_count": i + 1,
            "owner_id": "test_owner",
        }
        for i in range(n)
    ]


def _make_relations(entity_ids: list[str], rtype: str = "uses") -> list[dict]:
    """Return a chain: 0→1, 1→2, … (n-2)→(n-1)."""
    return [
        {
            "source_id": entity_ids[i],
            "target_id": entity_ids[i + 1],
            "relation_type": rtype,
            "confidence": 1.0,
        }
        for i in range(len(entity_ids) - 1)
    ]


# ── build_entity_graph ─────────────────────────────────────────────────────


class TestBuildEntityGraph:
    def test_nodes_added(self):
        entities = _make_entities(4)
        G = build_entity_graph(entities, [])
        assert G.number_of_nodes() == 4

    def test_relations_become_edges(self):
        entities = _make_entities(3)
        ids = [e["id"] for e in entities]
        relations = _make_relations(ids)
        G = build_entity_graph(entities, relations)
        assert G.number_of_edges() == 2

    def test_entity_attrs_preserved(self):
        entities = _make_entities(2)
        G = build_entity_graph(entities, [])
        assert G.nodes["ent-0"]["entity_type"] == "technology"
        assert G.nodes["ent-0"]["memory_count"] == 1
        assert G.nodes["ent-1"]["label"] == "Entity 1"

    def test_relation_type_on_edge(self):
        entities = _make_entities(2)
        relations = [
            {"source_id": "ent-0", "target_id": "ent-1",
             "relation_type": "depends-on", "confidence": 0.9}
        ]
        G = build_entity_graph(entities, relations)
        assert G["ent-0"]["ent-1"]["relation_type"] == "depends-on"
        assert G["ent-0"]["ent-1"]["weight"] == pytest.approx(0.9)

    def test_empty_graph(self):
        G = build_entity_graph([], [])
        assert G.number_of_nodes() == 0
        assert G.number_of_edges() == 0

    def test_skips_unknown_entity_in_relation(self):
        """Relations referencing entities not in the node list are dropped."""
        entities = _make_entities(2)
        relations = [
            {"source_id": "ent-0", "target_id": "ent-MISSING",
             "relation_type": "uses", "confidence": 1.0}
        ]
        G = build_entity_graph(entities, relations)
        assert G.number_of_edges() == 0


# ── analyze() auto-detection ───────────────────────────────────────────────


class TestAnalyzeEntityMode:
    def _entity_graph(self) -> nx.Graph:
        entities = _make_entities(5)
        ids = [e["id"] for e in entities]
        relations = _make_relations(ids)
        relations.append(
            {"source_id": ids[0], "target_id": ids[2],
             "relation_type": "is-part-of", "confidence": 1.0}
        )
        G = build_entity_graph(entities, relations)
        detect_communities(G)
        return G

    def test_god_node_most_connected(self):
        G = self._entity_graph()
        result = analyze(G)
        # Chain: 0→1, 1→2, 2→3, 3→4  +  extra 0→2
        # Degrees: ent-2 connects to ent-1, ent-3, ent-0 → highest degree
        assert result["god_nodes"][0]["id"] == "ent-2"

    def test_dominant_domain_uses_entity_type(self):
        G = self._entity_graph()
        result = analyze(G)
        for c in result["communities"]:
            # entity_type values should appear, NOT memory-type values
            assert c["dominant_domain"] in (
                "technology", "project", "person", "concept", "decision", "tool", "unknown"
            )

    def test_stats_correct(self):
        G = self._entity_graph()
        result = analyze(G)
        assert result["stats"]["node_count"] == 5
        assert result["stats"]["edge_count"] == 5  # 4 chain + 1 extra


# ── render_entity_html ─────────────────────────────────────────────────────


class TestRenderEntityHtml:
    def _minimal(self):
        entities = _make_entities(3)
        ids = [e["id"] for e in entities]
        relations = _make_relations(ids, "uses")
        G = build_entity_graph(entities, relations)
        detect_communities(G)
        graph_json = to_node_link_json(G)
        analysis = analyze(G)
        return graph_json, analysis

    def test_returns_string(self):
        gj, an = self._minimal()
        html = render_entity_html(gj, an)
        assert isinstance(html, str)

    def test_contains_d3(self):
        gj, an = self._minimal()
        html = render_entity_html(gj, an)
        assert "d3.v7.min.js" in html

    def test_entity_type_colors_embedded(self):
        gj, an = self._minimal()
        html = render_entity_html(gj, an)
        assert "ENTITY_COLORS" in html
        assert "technology" in html

    def test_node_ids_embedded(self):
        gj, an = self._minimal()
        html = render_entity_html(gj, an)
        assert "ent-0" in html

    def test_custom_title(self):
        gj, an = self._minimal()
        html = render_entity_html(gj, an, title="My Entity Graph")
        assert "My Entity Graph" in html

    def test_valid_html(self):
        gj, an = self._minimal()
        html = render_entity_html(gj, an)
        assert html.strip().startswith("<!DOCTYPE html>")
        assert "</html>" in html

    def test_relation_type_in_output(self):
        """relation_type must appear in the embedded JSON so the JS edge tooltip works."""
        gj, an = self._minimal()
        html = render_entity_html(gj, an)
        assert "relation_type" in html or "uses" in html

    def test_json_serializable_graph(self):
        gj, an = self._minimal()
        assert "nodes" in gj
        json.dumps(gj)  # must not raise


# ── entity_extractor parsing (pure function, no LLM, no DB) ──────────────
# _parse_entity_json is a pure function (json + re only); we reproduce it
# here so the tests run locally without pgvector installed.

import json as _json
import re as _re


def _parse_entity_json_local(raw: str):
    """Local copy of entity_extractor._parse_entity_json for unit testing."""
    if "```" in raw:
        parts = raw.split("```")
        for part in parts[1::2]:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                try:
                    return _json.loads(part)
                except _json.JSONDecodeError:
                    pass
    raw = raw.strip()
    try:
        return _json.loads(raw)
    except _json.JSONDecodeError:
        pass
    start = raw.find("{")
    if start == -1:
        return None
    depth, end = 0, start
    for i, ch in enumerate(raw[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if depth != 0:
        return None
    fragment = raw[start:end]
    cleaned = _re.sub(r",\s*([}\]])", r"\1", fragment)
    try:
        return _json.loads(cleaned)
    except _json.JSONDecodeError:
        return None


class TestParseEntityJson:
    """Test the JSON-parsing logic used by entity_extractor in isolation."""

    def _parse(self, raw: str):
        return _parse_entity_json_local(raw)

    def test_valid_json(self):
        raw = '{"entities": [{"label": "A", "type": "technology"}], "relations": []}'
        result = self._parse(raw)
        assert result is not None
        assert result["entities"][0]["label"] == "A"

    def test_markdown_fence(self):
        raw = '```json\n{"entities":[],"relations":[]}\n```'
        result = self._parse(raw)
        assert result is not None

    def test_trailing_comma_repair(self):
        raw = '{"entities": [{"label": "A", "type": "tool"},], "relations": []}'
        result = self._parse(raw)
        assert result is not None

    def test_garbage_prefix(self):
        raw = 'Sure! Here is the JSON:\n{"entities":[],"relations":[]}'
        result = self._parse(raw)
        assert result is not None

    def test_unparseable_returns_none(self):
        result = self._parse("this is not json at all")
        assert result is None
