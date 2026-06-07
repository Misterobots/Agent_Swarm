"""MemPalace graph helpers — pure functions, no DB coupling.

Similarity graph pipeline (memory nodes, cosine-similarity edges):
    build_graph(nodes, edges)        -> nx.Graph
    detect_communities(G)            -> G  (community attr added in-place)
    analyze(G)                       -> dict
    to_node_link_json(G)             -> dict  (graphify-compatible)
    render_html(graph_json, analysis, title)  -> str  (D3 force page)

Entity graph pipeline (entity nodes, typed-relation edges):
    build_entity_graph(entities, relations) -> nx.Graph
    detect_communities(G)                   -> G  (same function, reused)
    analyze(G)                              -> dict  (same function, auto-detects mode)
    to_node_link_json(G)                    -> dict  (same function)
    render_entity_html(graph_json, analysis, title) -> str  (D3 entity page)
"""

from __future__ import annotations

import json
from typing import Any

import networkx as nx


# ── Community detection ────────────────────────────────────────────────────

def detect_communities(G: nx.Graph) -> nx.Graph:
    """Assign an integer 'community' attr to every node in-place.

    Uses NetworkX greedy_modularity_communities — no extra deps required.
    Falls back to one community per connected component when the graph is
    very sparse (< 3 nodes or no edges).
    Returns G for chaining.
    """
    if len(G) == 0:
        return G

    if G.number_of_edges() == 0:
        # No edges: assign each node its own community (sparse forest)
        for i, n in enumerate(G.nodes()):
            G.nodes[n]["community"] = i
        return G

    communities = list(
        nx.community.greedy_modularity_communities(G, weight="weight")
    )
    for cid, members in enumerate(communities):
        for node in members:
            G.nodes[node]["community"] = cid

    return G


# ── Graph builder ──────────────────────────────────────────────────────────

def build_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> nx.Graph:
    """Build a weighted undirected NetworkX graph.

    Node dicts must have 'id' plus any attrs you want on the node.
    Edge dicts must have 'source', 'target', and optionally 'weight'.
    """
    G = nx.Graph()
    for n in nodes:
        nid = n["id"]
        attrs = {k: v for k, v in n.items() if k != "id"}
        G.add_node(nid, **attrs)
    for e in edges:
        G.add_edge(e["source"], e["target"], weight=e.get("weight", 1.0))
    return G


# ── Analysis ───────────────────────────────────────────────────────────────

def analyze(G: nx.Graph) -> dict[str, Any]:
    """Return analysis dict mirroring graphify's analyze.py output shape.

    Sections:
        god_nodes  — top-10 nodes by weighted degree
        bridges    — top-5 nodes by betweenness centrality (cross-cluster)
        communities — per-cluster summary (dominant domain / type / size)
        stats      — aggregate graph metrics
    """
    if len(G) == 0:
        return {
            "god_nodes": [],
            "bridges": [],
            "communities": [],
            "stats": {"node_count": 0, "edge_count": 0,
                      "community_count": 0, "density": 0.0},
        }

    # Weighted degree
    degree = dict(G.degree(weight="weight"))
    top_degree = sorted(degree.items(), key=lambda x: x[1], reverse=True)[:10]

    # Betweenness centrality — O(V·E) but fine at our scale (< 2000 nodes)
    betweenness = nx.betweenness_centrality(G, weight="weight", normalized=True)
    top_between = sorted(
        betweenness.items(), key=lambda x: x[1], reverse=True
    )[:5]

    # Community summary
    communities: dict[int, list[str]] = {}
    for node in G.nodes():
        cid = G.nodes[node].get("community", 0)
        communities.setdefault(cid, []).append(node)

    entity_mode = _is_entity_graph(G)
    domain_attr = "entity_type" if entity_mode else "domain"
    type_attr   = "entity_type" if entity_mode else "memory_type"

    community_list = [
        {
            "id": cid,
            "size": len(members),
            "dominant_domain": _dominant_attr(G, members, domain_attr),
            "dominant_type":   _dominant_attr(G, members, type_attr),
        }
        for cid, members in sorted(communities.items())
    ]

    god_nodes = [
        {
            "id": nid,
            "label": G.nodes[nid].get("label", nid),
            "degree": round(deg, 3),
            "community": G.nodes[nid].get("community", 0),
        }
        for nid, deg in top_degree
    ]

    bridge_nodes = [
        {
            "id": nid,
            "label": G.nodes[nid].get("label", nid),
            "betweenness": round(score, 4),
            "community": G.nodes[nid].get("community", 0),
        }
        for nid, score in top_between
    ]

    return {
        "god_nodes": god_nodes,
        "bridges": bridge_nodes,
        "communities": community_list,
        "stats": {
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
            "community_count": len(communities),
            "density": round(nx.density(G), 4),
        },
    }


def _dominant_attr(G: nx.Graph, node_ids: list[str], attr: str) -> str:
    counts: dict[str, int] = {}
    for nid in node_ids:
        val = G.nodes[nid].get(attr) or "unknown"
        counts[val] = counts.get(val, 0) + 1
    return max(counts, key=lambda k: counts[k]) if counts else "unknown"


def _is_entity_graph(G: nx.Graph) -> bool:
    """True when the graph holds entity nodes (not memory similarity nodes)."""
    sample = next(iter(G.nodes()), None)
    return bool(sample and G.nodes[sample].get("entity_type") is not None)


# ── Export ─────────────────────────────────────────────────────────────────

def to_node_link_json(G: nx.Graph) -> dict[str, Any]:
    """Export as graphify-compatible node-link JSON.

    NetworkX node_link_data returns {directed, multigraph, graph, nodes, links}.
    The 'links' key contains {source, target, weight}.
    """
    return nx.node_link_data(G)


# ── HTML visualisation ─────────────────────────────────────────────────────

# 20-colour palette (Tableau-inspired, dark-background friendly)
_COMMUNITY_COLORS = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
    "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
    "#86bcb6", "#f1ce63", "#499894", "#fabfd2", "#b6992d",
    "#d37295", "#bcbd22", "#17becf", "#aec7e8", "#ffbb78",
]


def render_html(
    graph_json: dict[str, Any],
    analysis: dict[str, Any],
    title: str = "MemPalace Knowledge Graph",
) -> str:
    """Return a self-contained D3 v7 force-directed page.

    Features:
      - Nodes sized by access_count, coloured by community
      - Hover tooltip shows full content_preview
      - Click-to-select panel in sidebar
      - Text search filter (dims non-matching nodes)
      - Drag, pan, zoom
      - God-node and community legend in sidebar
    """
    data_json = json.dumps(graph_json)
    analysis_json = json.dumps(analysis)
    colors_json = json.dumps(_COMMUNITY_COLORS)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'Segoe UI',-apple-system,BlinkMacSystemFont,sans-serif;
         background:#0f1117;color:#e0e0e0;height:100vh;overflow:hidden;
         display:flex;flex-direction:column}}
    #header{{padding:10px 18px;background:#1a1d27;border-bottom:1px solid #2d3148;
             display:flex;align-items:center;gap:12px;flex-shrink:0}}
    #header h1{{font-size:1rem;font-weight:600;color:#c8d4f5;letter-spacing:.02em}}
    .chip{{font-size:.72rem;background:#252840;color:#9ba3c8;padding:3px 9px;
           border-radius:11px;border:1px solid #353a5e;white-space:nowrap}}
    #controls{{margin-left:auto;display:flex;gap:7px}}
    button{{padding:4px 13px;background:#2e3462;color:#c8d4f5;border:1px solid #434a7a;
            border-radius:6px;font-size:.78rem;cursor:pointer;transition:background .15s}}
    button:hover{{background:#3d457f}}
    #main{{display:flex;flex:1;overflow:hidden;min-height:0}}
    /* min-width:0 prevents graph from squeezing out the sidebar in flex */
    #graph-container{{flex:1;min-width:0;position:relative;overflow:hidden}}
    svg{{width:100%;height:100%;display:block}}
    /* zoom hint badge */
    #zoom-hint{{position:absolute;bottom:12px;left:50%;transform:translateX(-50%);
                background:rgba(30,34,53,.85);color:#6872a8;font-size:.72rem;
                padding:4px 12px;border-radius:10px;pointer-events:none;
                border:1px solid #2d3148;transition:opacity .4s}}
    #zoom-hint.hidden{{opacity:0}}
    #sidebar{{width:260px;background:#1a1d27;border-left:1px solid #2d3148;
              overflow-y:auto;flex-shrink:0;font-size:.81rem}}
    .panel{{padding:13px 15px;border-bottom:1px solid #2d3148}}
    .panel h3{{font-size:.68rem;text-transform:uppercase;letter-spacing:.1em;
               color:#6872a8;margin-bottom:9px}}
    .god-item{{display:flex;align-items:center;gap:7px;margin-bottom:5px;
               cursor:pointer;border-radius:5px;padding:2px 4px}}
    .god-item:hover{{background:#252840}}
    .rank{{font-size:.66rem;color:#4e5582;width:15px;flex-shrink:0}}
    .node-label{{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#c8d4f5}}
    .deg{{font-size:.66rem;color:#6872a8;flex-shrink:0}}
    .comm-item{{display:flex;align-items:center;gap:7px;margin-bottom:4px}}
    .dot{{width:9px;height:9px;border-radius:50%;flex-shrink:0}}
    .comm-label{{flex:1;color:#a0a8cc;white-space:nowrap;overflow:hidden;
                 text-overflow:ellipsis;font-size:.76rem}}
    .comm-size{{color:#4e5582;font-size:.66rem}}
    #tooltip{{position:fixed;background:#1e2235;border:1px solid #3d4470;
              border-radius:8px;padding:9px 13px;max-width:300px;
              pointer-events:none;opacity:0;transition:opacity .15s;
              font-size:.79rem;z-index:100;box-shadow:0 4px 18px rgba(0,0,0,.5)}}
    #tooltip.vis{{opacity:1}}
    .tt-meta{{font-size:.68rem;color:#6872a8;margin-bottom:3px}}
    .tt-body{{color:#c8d4f5;line-height:1.45}}
    .link{{stroke-opacity:.3}}
    .node circle{{stroke-width:1.5px}}
    .node text{{font-size:9px;fill:#8890b8;pointer-events:none;user-select:none}}
    #search{{width:100%;padding:5px 9px;background:#252840;border:1px solid #353a5e;
             border-radius:5px;color:#c8d4f5;font-size:.78rem;margin-bottom:9px}}
    #search::placeholder{{color:#4e5582}}
    #search:focus{{outline:none;border-color:#5566aa}}
    #sel-panel{{display:none}}
    #sel-meta{{font-size:.69rem;color:#6872a8;margin-bottom:5px}}
    #sel-body{{color:#c8d4f5;line-height:1.5;word-break:break-word}}
  </style>
</head>
<body>
<div id="header">
  <h1>🧠 {title}</h1>
  <span class="chip" id="c-nodes">—</span>
  <span class="chip" id="c-edges">—</span>
  <span class="chip" id="c-comm">—</span>
  <div id="controls">
    <button onclick="resetZoom()">Reset</button>
    <button onclick="toggleLabels()">Labels</button>
  </div>
</div>
<div id="main">
  <div id="graph-container">
    <svg id="svg"></svg>
    <div id="zoom-hint">Scroll to zoom · Labels appear at 2×</div>
  </div>
  <div id="sidebar">
    <div class="panel">
      <h3>Search</h3>
      <input type="text" id="search" placeholder="Filter by content, domain…" oninput="filterNodes(this.value)">
    </div>
    <div class="panel">
      <h3>God Nodes</h3>
      <div id="god-list"></div>
    </div>
    <div class="panel">
      <h3>Communities</h3>
      <div id="comm-list"></div>
    </div>
    <div class="panel" id="sel-panel">
      <h3>Selected</h3>
      <div id="sel-meta"></div>
      <div id="sel-body"></div>
    </div>
  </div>
</div>
<div id="tooltip"></div>

<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const G = {data_json};
const A = {analysis_json};
const COLORS = {colors_json};
const svg = d3.select("#svg");
const root = svg.append("g");
// Labels start OFF — they appear automatically when zoomed past LABEL_ZOOM_THRESHOLD
// or when the user hits the Labels button to force-show them.
let showLabels = false, manualLabelOverride = false, sim, zoomK = 1;
const LABEL_ZOOM_THRESHOLD = 2.0;   // labels auto-appear at 2× zoom

const W = () => document.getElementById("graph-container").clientWidth;
const H = () => document.getElementById("graph-container").clientHeight;
const color = c => COLORS[(c || 0) % COLORS.length];
const radius = d => Math.max(5, Math.min(22, 5 + Math.log1p(d.access_count || 0) * 1.8));

// ── Sidebar ───────────────────────────────────────────────────────
(function buildSidebar() {{
  const s = A.stats || {{}};
  document.getElementById("c-nodes").textContent = (s.node_count || 0) + " nodes";
  document.getElementById("c-edges").textContent = (s.edge_count || 0) + " edges";
  document.getElementById("c-comm").textContent  = (s.community_count || 0) + " clusters";

  const gl = document.getElementById("god-list");
  (A.god_nodes || []).slice(0, 8).forEach((n, i) => {{
    const d = document.createElement("div");
    d.className = "god-item";
    d.innerHTML = `<span class="rank">#${{i+1}}</span>
                   <span class="node-label" title="${{n.label}}">${{n.label}}</span>
                   <span class="deg">${{n.degree.toFixed(2)}}</span>`;
    d.onclick = () => focusNode(n.id);
    gl.appendChild(d);
  }});

  const cl = document.getElementById("comm-list");
  (A.communities || []).forEach(c => {{
    const lbl = (c.dominant_domain && c.dominant_domain !== "unknown")
      ? c.dominant_domain + " / " + c.dominant_type
      : "Community " + c.id;
    const d = document.createElement("div");
    d.className = "comm-item";
    d.innerHTML = `<span class="dot" style="background:${{color(c.id)}}"></span>
                   <span class="comm-label" title="${{lbl}}">${{lbl}}</span>
                   <span class="comm-size">${{c.size}}</span>`;
    cl.appendChild(d);
  }});
}})();

// ── Graph ─────────────────────────────────────────────────────────
(function initGraph() {{
  const nodes = (G.nodes || []).map(n => ({{...n}}));
  const links = (G.links || G.edges || []).map(l => ({{...l}}));
  const N = nodes.length;

  // Scale repulsion to node count so sparse graphs don't fly apart
  // and dense graphs don't collapse: roughly -80 per node, capped at -700
  const chargeStrength = -Math.min(700, Math.max(120, N * 1.4));

  const linkSel = root.append("g").selectAll("line").data(links).join("line")
    .attr("class", "link")
    .attr("stroke", "#3d4470")
    .attr("stroke-width", d => Math.max(0.4, (d.weight || 0.5) * 1.8));

  const nodeG = root.append("g").selectAll("g").data(nodes).join("g")
    .attr("class", "node")
    .call(d3.drag()
      .on("start", (e, d) => {{ if (!e.active) sim.alphaTarget(.3).restart(); d.fx=d.x; d.fy=d.y; }})
      .on("drag",  (e, d) => {{ d.fx=e.x; d.fy=e.y; }})
      .on("end",   (e, d) => {{ if (!e.active) sim.alphaTarget(0); d.fx=null; d.fy=null; }}));

  nodeG.append("circle")
    .attr("r", radius)
    .attr("fill", d => color(d.community))
    .attr("stroke", d => d3.color(color(d.community)).darker(.6))
    .on("mouseover", showTip)
    .on("mousemove", moveTip)
    .on("mouseout",  hideTip)
    .on("click", selectNode);

  // Labels start hidden — toggled by zoom level or the Labels button
  nodeG.append("text")
    .attr("x", d => radius(d) + 3)
    .attr("y", "0.35em")
    .attr("display", "none")
    .text(d => (d.label || "").slice(0, 38));

  sim = d3.forceSimulation(nodes)
    .force("link",    d3.forceLink(links).id(d => d.id)
                        .distance(110)
                        .strength(d => (d.weight || .5) * .3))
    .force("charge",  d3.forceManyBody().strength(chargeStrength))
    .force("center",  d3.forceCenter(W() / 2, H() / 2))
    .force("collide", d3.forceCollide().radius(d => radius(d) + 14).strength(0.8))
    .alphaDecay(0.025)   // slightly faster settling than default 0.0228
    .on("tick", () => {{
      linkSel.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
             .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
      nodeG.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
    }});

  // Zoom: hide/show hint badge and auto-manage labels by zoom level
  const zoomBehavior = d3.zoom().scaleExtent([.05, 12])
    .on("zoom", e => {{
      root.attr("transform", e.transform);
      zoomK = e.transform.k;
      // Auto-show labels when zoomed in, unless user forced them off
      const autoShow = zoomK >= LABEL_ZOOM_THRESHOLD;
      const vis = manualLabelOverride ? showLabels : autoShow;
      d3.selectAll(".node text").attr("display", vis ? null : "none");
      // Fade out hint once user has zoomed
      if (zoomK !== 1) document.getElementById("zoom-hint").classList.add("hidden");
    }});
  svg.call(zoomBehavior);
  window._zoomBehavior = zoomBehavior;
  window._nodeG = nodeG;
  window._nodes = nodes;
}})();

// ── Tooltip ───────────────────────────────────────────────────────
const tip = document.getElementById("tooltip");
function showTip(ev, d) {{
  tip.innerHTML = `<div class="tt-meta">${{d.memory_type||""}} · ${{d.domain||""}}</div>
                   <div class="tt-body">${{(d.content_preview||d.label||"").slice(0,220)}}</div>`;
  tip.classList.add("vis"); moveTip(ev);
}}
function moveTip(ev) {{
  tip.style.left = Math.min(ev.clientX+14, window.innerWidth-315) + "px";
  tip.style.top  = Math.min(ev.clientY-8,  window.innerHeight-110) + "px";
}}
function hideTip() {{ tip.classList.remove("vis"); }}

function selectNode(ev, d) {{
  document.getElementById("sel-panel").style.display = "block";
  document.getElementById("sel-meta").textContent =
    `${{d.memory_type}} · ${{d.domain}} · accessed ${{d.access_count||0}}×`;
  document.getElementById("sel-body").textContent = d.content_preview || d.label || "";
  window._nodeG.selectAll("circle")
    .attr("stroke-width", n => n.id === d.id ? 3 : 1.5)
    .attr("stroke", n => n.id === d.id
      ? "#ffffff"
      : d3.color(COLORS[(n.community||0) % COLORS.length]).darker(.6));
}}

// ── Controls ──────────────────────────────────────────────────────
function resetZoom() {{
  svg.transition().duration(500).call(
    window._zoomBehavior.transform,
    d3.zoomIdentity.translate(W()/2, H()/2).scale(0.8)
  );
}}
function toggleLabels() {{
  // Manual override: flip state and lock it regardless of zoom level
  showLabels = !showLabels;
  manualLabelOverride = true;
  d3.selectAll(".node text").attr("display", showLabels ? null : "none");
  // Reset manual override when user zooms (let auto-mode take back over)
  // after a short delay so the click doesn't immediately trigger zoom handler
}}
function focusNode(id) {{
  const n = window._nodes.find(n => n.id === id);
  if (!n || n.x == null) return;
  svg.transition().duration(600).call(
    window._zoomBehavior.transform,
    d3.zoomIdentity.translate(W()/2 - n.x * 2.2, H()/2 - n.y * 2.2).scale(2.2)
  );
}}
function filterNodes(q) {{
  q = q.toLowerCase().trim();
  window._nodeG.selectAll("circle").attr("opacity", d =>
    !q || (d.label||"").toLowerCase().includes(q) ||
    (d.content_preview||"").toLowerCase().includes(q) ||
    (d.domain||"").toLowerCase().includes(q) ? 1 : .07);
  window._nodeG.selectAll("text").attr("opacity", d =>
    !q || (d.label||"").toLowerCase().includes(q) ? 1 : .07);
}}
window.addEventListener("resize", () => {{
  if (sim) sim.force("center", d3.forceCenter(W()/2, H()/2)).alpha(.25).restart();
}});
</script>
</body>
</html>"""


# ── Entity graph builder ───────────────────────────────────────────────────

def build_entity_graph(
    entities: list[dict[str, Any]],
    relations: list[dict[str, Any]],
) -> nx.Graph:
    """Build a weighted undirected graph from extracted entities and typed relations.

    Entity dicts must have 'id' plus optional attrs:
        label, entity_type, memory_count, owner_id
    Relation dicts must have 'source_id', 'target_id', and optionally:
        relation_type, confidence (used as edge weight)
    """
    G = nx.Graph()
    for e in entities:
        eid = e["id"]
        attrs = {k: v for k, v in e.items() if k != "id"}
        G.add_node(eid, **attrs)
    for r in relations:
        src = r.get("source_id") or r.get("source")
        tgt = r.get("target_id") or r.get("target")
        if src and tgt and src in G and tgt in G:
            G.add_edge(
                src, tgt,
                relation_type=r.get("relation_type", "related-to"),
                weight=float(r.get("confidence", 1.0)),
            )
    return G


# ── Entity graph HTML renderer ─────────────────────────────────────────────

# Fixed color palette keyed by entity_type
_ENTITY_TYPE_COLORS: dict[str, str] = {
    "technology": "#4e79a7",   # blue
    "project":    "#f28e2b",   # orange
    "person":     "#59a14f",   # green
    "concept":    "#b07aa1",   # purple
    "decision":   "#edc948",   # yellow
    "tool":       "#76b7b2",   # teal
}
_ENTITY_TYPE_COLORS_JSON = json.dumps(_ENTITY_TYPE_COLORS)


def render_entity_html(
    graph_json: dict[str, Any],
    analysis: dict[str, Any],
    title: str = "MemPalace Knowledge Graph",
) -> str:
    """Return a self-contained D3 v7 entity knowledge graph page.

    Key design principles:
      - Read-only: NO dragging. The graph is a map, not a whiteboard.
      - Pre-computed layout: simulation runs to convergence before first paint,
        so the user sees the organised result immediately (never a random cloud).
      - Auto fit-to-view: the whole graph fills the viewport on load.
      - Nodes coloured by entity_type (fixed palette).
      - Node labels always visible (entity names are short).
      - Edge hover shows typed relation (A → uses → B).
      - Zoom / pan for exploration; Reset fits back to overview.
    """
    data_json     = json.dumps(graph_json)
    analysis_json = json.dumps(analysis)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'Segoe UI',-apple-system,BlinkMacSystemFont,sans-serif;
         background:#0f1117;color:#e0e0e0;height:100vh;overflow:hidden;
         display:flex;flex-direction:column}}
    #header{{padding:10px 18px;background:#1a1d27;border-bottom:1px solid #2d3148;
             display:flex;align-items:center;gap:12px;flex-shrink:0}}
    #header h1{{font-size:1rem;font-weight:600;color:#c8d4f5;letter-spacing:.02em}}
    .chip{{font-size:.72rem;background:#252840;color:#9ba3c8;padding:3px 9px;
           border-radius:11px;border:1px solid #353a5e;white-space:nowrap}}
    #controls{{margin-left:auto;display:flex;gap:7px}}
    button{{padding:4px 13px;background:#2e3462;color:#c8d4f5;border:1px solid #434a7a;
            border-radius:6px;font-size:.78rem;cursor:pointer;transition:background .15s}}
    button:hover{{background:#3d457f}}
    #main{{display:flex;flex:1;overflow:hidden;min-height:0}}
    #graph-container{{flex:1;min-width:0;position:relative;overflow:hidden;cursor:grab}}
    #graph-container:active{{cursor:grabbing}}
    svg{{width:100%;height:100%;display:block}}
    #sidebar{{width:270px;background:#1a1d27;border-left:1px solid #2d3148;
              overflow-y:auto;flex-shrink:0;font-size:.81rem}}
    .panel{{padding:13px 15px;border-bottom:1px solid #2d3148}}
    .panel h3{{font-size:.68rem;text-transform:uppercase;letter-spacing:.1em;
               color:#6872a8;margin-bottom:9px}}
    .god-item{{display:flex;align-items:center;gap:7px;margin-bottom:5px;
               cursor:pointer;border-radius:5px;padding:2px 4px;transition:background .1s}}
    .god-item:hover{{background:#252840}}
    .rank{{font-size:.66rem;color:#4e5582;width:15px;flex-shrink:0;text-align:right}}
    .node-label{{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#c8d4f5}}
    .deg{{font-size:.66rem;color:#6872a8;flex-shrink:0}}
    .type-item{{display:flex;align-items:center;gap:8px;margin-bottom:5px}}
    .dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}
    .type-label{{flex:1;color:#a0a8cc;font-size:.77rem;text-transform:capitalize}}
    .type-count{{color:#4e5582;font-size:.68rem}}
    #tooltip{{position:fixed;background:#1e2235;border:1px solid #3d4470;
              border-radius:8px;padding:9px 13px;max-width:320px;
              pointer-events:none;opacity:0;transition:opacity .12s;
              font-size:.79rem;z-index:100;box-shadow:0 4px 18px rgba(0,0,0,.5)}}
    #tooltip.vis{{opacity:1}}
    .tt-meta{{font-size:.68rem;color:#6872a8;margin-bottom:3px}}
    .tt-body{{color:#c8d4f5;line-height:1.45}}
    .tt-rel{{font-size:.69rem;color:#7880aa;margin-top:5px;line-height:1.7}}
    .node circle{{stroke-width:1.5px;cursor:pointer;transition:stroke .1s,stroke-width .1s}}
    .node text{{font-size:10px;fill:#c8d4f5;pointer-events:none;user-select:none;
                text-shadow:0 1px 4px #0f1117,0 -1px 4px #0f1117,
                            1px 0 4px #0f1117,-1px 0 4px #0f1117}}
    #search{{width:100%;padding:5px 9px;background:#252840;border:1px solid #353a5e;
             border-radius:5px;color:#c8d4f5;font-size:.78rem;margin-bottom:9px}}
    #search::placeholder{{color:#4e5582}}
    #search:focus{{outline:none;border-color:#5566aa}}
    #sel-panel{{display:none}}
    #sel-meta{{font-size:.69rem;color:#6872a8;margin-bottom:5px}}
    #sel-body{{color:#c8d4f5;line-height:1.5;word-break:break-word;font-weight:600}}
    #sel-rels{{margin-top:9px;font-size:.72rem;color:#7880aa;line-height:1.8}}
  </style>
</head>
<body>
<div id="header">
  <h1>🧠 {title}</h1>
  <span class="chip" id="c-nodes">—</span>
  <span class="chip" id="c-edges">—</span>
  <span class="chip" id="c-comm">—</span>
  <div id="controls">
    <button onclick="fitView()">Reset View</button>
  </div>
</div>
<div id="main">
  <div id="graph-container"><svg id="svg"></svg></div>
  <div id="sidebar">
    <div class="panel">
      <h3>Search</h3>
      <input type="text" id="search" placeholder="Filter by name or type…"
             oninput="filterNodes(this.value)">
    </div>
    <div class="panel">
      <h3>Entity Types</h3>
      <div id="type-legend"></div>
    </div>
    <div class="panel">
      <h3>Hub Entities</h3>
      <div id="god-list"></div>
    </div>
    <div class="panel" id="sel-panel">
      <h3>Selected</h3>
      <div id="sel-meta"></div>
      <div id="sel-body"></div>
      <div id="sel-rels"></div>
    </div>
  </div>
</div>
<div id="tooltip"></div>

<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
"use strict";
const G = {data_json};
const A = {analysis_json};
const ENTITY_COLORS = {_ENTITY_TYPE_COLORS_JSON};
const DEFAULT_COLOR = "#9b9b9b";

const svg   = d3.select("#svg");
const root  = svg.append("g");
const tip   = document.getElementById("tooltip");

const cw = () => document.getElementById("graph-container").clientWidth;
const ch = () => document.getElementById("graph-container").clientHeight;
const nodeColor  = d => ENTITY_COLORS[d.entity_type] || DEFAULT_COLOR;
const nodeRadius = d => Math.max(6, Math.min(26, 6 + Math.log1p(d.memory_count || 0) * 3.2));

// ── Stats chips ───────────────────────────────────────────────────
(function() {{
  const s = A.stats || {{}};
  document.getElementById("c-nodes").textContent = (s.node_count      || 0) + " entities";
  document.getElementById("c-edges").textContent = (s.edge_count      || 0) + " relations";
  document.getElementById("c-comm").textContent  = (s.community_count || 0) + " clusters";
}})();

// ── Entity-type legend ────────────────────────────────────────────
(function() {{
  const typeCounts = {{}};
  (G.nodes || []).forEach(n => {{
    typeCounts[n.entity_type] = (typeCounts[n.entity_type] || 0) + 1;
  }});
  const tl = document.getElementById("type-legend");
  Object.entries(typeCounts).sort((a, b) => b[1] - a[1]).forEach(([t, cnt]) => {{
    const el = document.createElement("div");
    el.className = "type-item";
    el.innerHTML =
      `<span class="dot" style="background:${{ENTITY_COLORS[t] || DEFAULT_COLOR}}"></span>` +
      `<span class="type-label">${{t}}</span>` +
      `<span class="type-count">${{cnt}}</span>`;
    tl.appendChild(el);
  }});
}})();

// ── Hub list ──────────────────────────────────────────────────────
(function() {{
  const gl = document.getElementById("god-list");
  (A.god_nodes || []).slice(0, 8).forEach((n, i) => {{
    const el = document.createElement("div");
    el.className = "god-item";
    el.innerHTML =
      `<span class="rank">#${{i + 1}}</span>` +
      `<span class="node-label" title="${{n.label}}">${{n.label}}</span>` +
      `<span class="deg">${{n.degree.toFixed(1)}}</span>`;
    el.onclick = () => focusNode(n.id);
    gl.appendChild(el);
  }});
}})();

// ═════════════════════════════════════════════════════════════════
// Graph — pre-compute layout, freeze, draw statically (read-only)
// ═════════════════════════════════════════════════════════════════
(function() {{
  const nodes = (G.nodes || []).map(n => ({{ ...n }}));
  const links = (G.links || G.edges || []).map(l => ({{ ...l }}));
  const N = nodes.length;
  if (N === 0) return;

  // ── 1. Seed positions so force layout starts near centre ─────────
  const W0 = cw(), H0 = ch();
  nodes.forEach(d => {{
    d.x = W0 / 2 + (Math.random() - 0.5) * Math.min(W0, H0) * 0.6;
    d.y = H0 / 2 + (Math.random() - 0.5) * Math.min(W0, H0) * 0.6;
  }});

  // ── 2. Build simulation (stopped — we tick manually) ─────────────
  //   Shorter link distance + stronger strength = tighter clusters.
  //   Gentle x/y forces keep orphan nodes from straying to infinity.
  const chargeStr = -Math.min(600, Math.max(180, N * 2.8));
  const sim = d3.forceSimulation(nodes)
    .force("link",    d3.forceLink(links).id(d => d.id).distance(65).strength(0.85))
    .force("charge",  d3.forceManyBody().strength(chargeStr))
    .force("center",  d3.forceCenter(W0 / 2, H0 / 2))
    .force("collide", d3.forceCollide().radius(d => nodeRadius(d) + 7).strength(0.85))
    .force("gx",      d3.forceX(W0 / 2).strength(0.04))
    .force("gy",      d3.forceY(H0 / 2).strength(0.04))
    .alphaDecay(0.0180)
    .stop();

  // ── 3. Run to convergence (headless — no animation) ──────────────
  //   iters = exact tick count until alpha < alphaMin
  const iters = Math.ceil(
    Math.log(sim.alphaMin()) / Math.log(1 - sim.alphaDecay())
  );
  for (let i = 0; i < iters; i++) sim.tick();

  // ── 4. Freeze all positions (makes graph read-only) ──────────────
  nodes.forEach(d => {{ d.fx = d.x; d.fy = d.y; }});

  // ── 5. Draw edges (static) ───────────────────────────────────────
  const linkSel = root.append("g").selectAll("line").data(links).join("line")
    .attr("stroke", "#4a5180")
    .attr("stroke-width", 1.4)
    .attr("stroke-opacity", 0.5)
    .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
    .attr("x2", d => d.target.x).attr("y2", d => d.target.y);

  // Transparent wider hit area for edge hover
  root.append("g").selectAll("line").data(links).join("line")
    .attr("stroke", "transparent")
    .attr("stroke-width", 16)
    .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
    .attr("x2", d => d.target.x).attr("y2", d => d.target.y)
    .on("mouseover", (ev, d) => showEdgeTip(ev, d, nodes))
    .on("mousemove", moveTip)
    .on("mouseout",  hideTip);

  // ── 6. Draw nodes (static, no drag) ─────────────────────────────
  const nodeG = root.append("g").selectAll("g").data(nodes).join("g")
    .attr("class", "node")
    .attr("transform", d => `translate(${{d.x}},${{d.y}})`);

  nodeG.append("circle")
    .attr("r", nodeRadius)
    .attr("fill", nodeColor)
    .attr("stroke", d => d3.color(nodeColor(d)).darker(0.5))
    .on("mouseover", (ev, d) => showNodeTip(ev, d, links, nodes))
    .on("mousemove", moveTip)
    .on("mouseout",  hideTip)
    .on("click",     (ev, d) => selectNode(ev, d, links, nodes, nodeG));

  nodeG.append("text")
    .attr("x", d => nodeRadius(d) + 5)
    .attr("y", "0.35em")
    .text(d => d.label || "");

  // ── 7. Zoom / pan (navigation only, no editing) ──────────────────
  const zoomBeh = d3.zoom()
    .scaleExtent([0.03, 20])
    .on("zoom", e => root.attr("transform", e.transform));
  svg.call(zoomBeh);
  window._zoomBeh  = zoomBeh;
  window._nodeG    = nodeG;
  window._nodes    = nodes;
  window._links    = links;

  // ── 8. Auto fit-to-view on first paint ───────────────────────────
  fitView(false);
}})();

// ── Fit graph to viewport ─────────────────────────────────────────
function fitView(animated) {{
  const nodes = window._nodes;
  if (!nodes || nodes.length === 0) return;
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  nodes.forEach(d => {{
    const r = nodeRadius(d);
    x0 = Math.min(x0, d.x - r); x1 = Math.max(x1, d.x + r);
    y0 = Math.min(y0, d.y - r); y1 = Math.max(y1, d.y + r);
  }});
  const pad = 60, W = cw(), H = ch();
  const scale = Math.min(0.92, Math.min(W / (x1 - x0 + pad * 2),
                                         H / (y1 - y0 + pad * 2)));
  const tx = W / 2 - scale * (x0 + x1) / 2;
  const ty = H / 2 - scale * (y0 + y1) / 2;
  const t  = d3.zoomIdentity.translate(tx, ty).scale(scale);
  if (animated === false) {{
    svg.call(window._zoomBeh.transform, t);
  }} else {{
    svg.transition().duration(550).call(window._zoomBeh.transform, t);
  }}
}}

// ── Tooltip helpers ───────────────────────────────────────────────
function moveTip(ev) {{
  tip.style.left = Math.min(ev.clientX + 16, window.innerWidth  - 340) + "px";
  tip.style.top  = Math.min(ev.clientY -  8, window.innerHeight - 150) + "px";
}}
function hideTip() {{ tip.classList.remove("vis"); }}

function _resolveId(ref) {{
  return ref !== null && typeof ref === "object" ? ref.id : ref;
}}

function showEdgeTip(ev, d, nodes) {{
  const src = nodes.find(n => n.id === _resolveId(d.source));
  const tgt = nodes.find(n => n.id === _resolveId(d.target));
  tip.innerHTML =
    `<div class="tt-meta">Relation</div>` +
    `<div class="tt-body"><b>${{src ? src.label : "?"}}</b>` +
    `<span style="color:#6872a8"> → ${{d.relation_type || "related-to"}} → </span>` +
    `<b>${{tgt ? tgt.label : "?"}}</b></div>`;
  tip.classList.add("vis"); moveTip(ev);
}}

function showNodeTip(ev, d, links, nodes) {{
  const out = links
    .filter(l => _resolveId(l.source) === d.id)
    .map(l => {{ const t = nodes.find(n => n.id === _resolveId(l.target));
                  return `→ ${{l.relation_type || "?"}} → ${{t ? t.label : "?"}}`; }});
  const inc = links
    .filter(l => _resolveId(l.target) === d.id)
    .map(l => {{ const s = nodes.find(n => n.id === _resolveId(l.source));
                  return `← ${{l.relation_type || "?"}} ← ${{s ? s.label : "?"}}`; }});
  const rels = [...out, ...inc].slice(0, 7).join("<br>");
  tip.innerHTML =
    `<div class="tt-meta">[${{d.entity_type || "unknown"}}] · ${{d.memory_count || 0}} memories</div>` +
    `<div class="tt-body"><b>${{d.label}}</b>` +
    (rels ? `<div class="tt-rel">${{rels}}</div>` : "") +
    `</div>`;
  tip.classList.add("vis"); moveTip(ev);
}}

// ── Selection panel ───────────────────────────────────────────────
function selectNode(ev, d, links, nodes, nodeG) {{
  document.getElementById("sel-panel").style.display = "block";
  document.getElementById("sel-meta").textContent =
    `[${{d.entity_type || "unknown"}}] · ${{d.memory_count || 0}} memories`;
  document.getElementById("sel-body").textContent = d.label || "";

  const out = links
    .filter(l => _resolveId(l.source) === d.id)
    .map(l => {{ const t = nodes.find(n => n.id === _resolveId(l.target));
                  return `→ ${{l.relation_type}} → ${{t ? t.label : "?"}}`; }});
  const inc = links
    .filter(l => _resolveId(l.target) === d.id)
    .map(l => {{ const s = nodes.find(n => n.id === _resolveId(l.source));
                  return `← ${{l.relation_type}} ← ${{s ? s.label : "?"}}`; }});
  document.getElementById("sel-rels").innerHTML =
    [...out, ...inc].join("<br>") || "(no relations)";

  nodeG.selectAll("circle")
    .attr("stroke-width", n => n.id === d.id ? 3.5 : 1.5)
    .attr("stroke", n => n.id === d.id
      ? "#ffffff"
      : d3.color(ENTITY_COLORS[n.entity_type] || DEFAULT_COLOR).darker(0.5));
}}

// ── Search / filter ───────────────────────────────────────────────
function filterNodes(q) {{
  q = q.toLowerCase().trim();
  window._nodeG.selectAll("circle").attr("opacity", d =>
    !q || (d.label || "").toLowerCase().includes(q) ||
    (d.entity_type || "").toLowerCase().includes(q) ? 1 : 0.06);
  window._nodeG.selectAll("text").attr("opacity", d =>
    !q || (d.label || "").toLowerCase().includes(q) ? 1 : 0.06);
}}

// ── Focus a specific node (from hub list click) ───────────────────
function focusNode(id) {{
  const n = (window._nodes || []).find(n => n.id === id);
  if (!n) return;
  const W = cw(), H = ch(), scale = 3.0;
  svg.transition().duration(650).call(
    window._zoomBeh.transform,
    d3.zoomIdentity.translate(W / 2 - n.x * scale, H / 2 - n.y * scale).scale(scale)
  );
}}
</script>
</body>
</html>"""
