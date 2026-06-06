"""Unit tests for app/graph.py — no DB, no network."""

from __future__ import annotations

import json
import math

import pytest
import networkx as nx

from app.graph import (
    build_graph,
    detect_communities,
    analyze,
    to_node_link_json,
    render_html,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_nodes(n: int) -> list[dict]:
    return [
        {"id": f"mem-{i}", "label": f"Memory {i}", "content_preview": f"Content {i}",
         "memory_type": "semantic", "domain": "coding" if i % 2 == 0 else "general",
         "agent_id": None, "owner_id": "test", "access_count": i, "created_at": ""}
        for i in range(n)
    ]


def _fully_connected_edges(nodes: list[dict], weight: float = 0.9) -> list[dict]:
    """Return all undirected pairs."""
    edges = []
    ids = [n["id"] for n in nodes]
    for i, src in enumerate(ids):
        for tgt in ids[i + 1:]:
            edges.append({"source": src, "target": tgt, "weight": weight})
    return edges


# ---------------------------------------------------------------------------
# build_graph
# ---------------------------------------------------------------------------

class TestBuildGraph:
    def test_nodes_added(self):
        nodes = _make_nodes(5)
        G = build_graph(nodes, [])
        assert G.number_of_nodes() == 5

    def test_edges_added_with_weight(self):
        nodes = _make_nodes(3)
        edges = [{"source": "mem-0", "target": "mem-1", "weight": 0.75}]
        G = build_graph(nodes, edges)
        assert G.number_of_edges() == 1
        assert G["mem-0"]["mem-1"]["weight"] == pytest.approx(0.75)

    def test_node_attrs_preserved(self):
        nodes = _make_nodes(2)
        G = build_graph(nodes, [])
        assert G.nodes["mem-0"]["domain"] == "coding"
        assert G.nodes["mem-0"]["access_count"] == 0

    def test_empty_graph(self):
        G = build_graph([], [])
        assert G.number_of_nodes() == 0
        assert G.number_of_edges() == 0


# ---------------------------------------------------------------------------
# detect_communities
# ---------------------------------------------------------------------------

class TestDetectCommunities:
    def test_two_cliques_separate(self):
        """Two dense cliques should land in different communities."""
        grp_a = _make_nodes(4)                            # mem-0..3
        grp_b = [{"id": f"mem-{i+4}", "label": f"Memory {i+4}",
                   "content_preview": "", "memory_type": "semantic",
                   "domain": "general", "agent_id": None, "owner_id": "test",
                   "access_count": 0, "created_at": ""}
                 for i in range(4)]                        # mem-4..7
        nodes = grp_a + grp_b
        # Dense within groups, one sparse bridge
        edges = _fully_connected_edges(grp_a, weight=0.95)
        edges += _fully_connected_edges(grp_b, weight=0.95)
        edges.append({"source": "mem-0", "target": "mem-4", "weight": 0.1})

        G = build_graph(nodes, edges)
        detect_communities(G)

        comms_a = {G.nodes[n["id"]]["community"] for n in grp_a}
        comms_b = {G.nodes[n["id"]]["community"] for n in grp_b}
        # The two cliques should *not* share the same community label
        assert comms_a.isdisjoint(comms_b), (
            f"Expected separate communities; got A={comms_a}, B={comms_b}"
        )

    def test_no_edges_each_own_community(self):
        nodes = _make_nodes(3)
        G = build_graph(nodes, [])
        detect_communities(G)
        comms = [G.nodes[n["id"]]["community"] for n in nodes]
        assert len(set(comms)) == 3, "Isolated nodes should each be their own community"

    def test_empty_graph_safe(self):
        G = build_graph([], [])
        detect_communities(G)  # should not raise


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------

class TestAnalyze:
    def test_god_node_is_hub(self):
        """The hub node (connected to all others) should be #1 god node."""
        nodes = _make_nodes(5)
        # mem-0 is the hub
        edges = [{"source": "mem-0", "target": f"mem-{i}", "weight": 0.9}
                 for i in range(1, 5)]
        G = build_graph(nodes, edges)
        detect_communities(G)
        result = analyze(G)
        assert result["god_nodes"][0]["id"] == "mem-0"

    def test_stats_correct(self):
        nodes = _make_nodes(4)
        edges = _fully_connected_edges(nodes)
        G = build_graph(nodes, edges)
        detect_communities(G)
        result = analyze(G)
        assert result["stats"]["node_count"] == 4
        assert result["stats"]["edge_count"] == 6  # C(4,2)
        assert result["stats"]["density"] == pytest.approx(1.0)

    def test_empty_graph_returns_safe_defaults(self):
        G = build_graph([], [])
        result = analyze(G)
        assert result["god_nodes"] == []
        assert result["stats"]["node_count"] == 0

    def test_community_dominant_domain(self):
        nodes = _make_nodes(4)  # mem-0,2 → coding; mem-1,3 → general
        edges = _fully_connected_edges(nodes)
        G = build_graph(nodes, edges)
        detect_communities(G)
        result = analyze(G)
        # All communities must have a dominant_domain set
        for c in result["communities"]:
            assert c["dominant_domain"] in ("coding", "general", "unknown")


# ---------------------------------------------------------------------------
# to_node_link_json
# ---------------------------------------------------------------------------

class TestToNodeLinkJson:
    def test_round_trip(self):
        nodes = _make_nodes(3)
        edges = [{"source": "mem-0", "target": "mem-1", "weight": 0.8}]
        G = build_graph(nodes, edges)
        data = to_node_link_json(G)
        assert "nodes" in data
        assert "links" in data or "edges" in data
        assert len(data["nodes"]) == 3

    def test_json_serialisable(self):
        nodes = _make_nodes(5)
        edges = _fully_connected_edges(nodes)
        G = build_graph(nodes, edges)
        data = to_node_link_json(G)
        # Should not raise
        json.dumps(data)


# ---------------------------------------------------------------------------
# render_html
# ---------------------------------------------------------------------------

class TestRenderHtml:
    def _minimal_graph(self) -> tuple[dict, dict]:
        nodes = _make_nodes(3)
        edges = [{"source": "mem-0", "target": "mem-1", "weight": 0.8}]
        G = build_graph(nodes, edges)
        detect_communities(G)
        graph_json = to_node_link_json(G)
        analysis = analyze(G)
        return graph_json, analysis

    def test_returns_string(self):
        gj, an = self._minimal_graph()
        html = render_html(gj, an)
        assert isinstance(html, str)

    def test_contains_d3_script(self):
        gj, an = self._minimal_graph()
        html = render_html(gj, an)
        assert "d3.v7.min.js" in html

    def test_contains_data_json(self):
        gj, an = self._minimal_graph()
        html = render_html(gj, an)
        # At minimum the node ids should appear in the embedded JSON
        assert "mem-0" in html

    def test_custom_title(self):
        gj, an = self._minimal_graph()
        html = render_html(gj, an, title="My Test Graph")
        assert "My Test Graph" in html

    def test_valid_html_structure(self):
        gj, an = self._minimal_graph()
        html = render_html(gj, an)
        assert html.strip().startswith("<!DOCTYPE html>")
        assert "</html>" in html
