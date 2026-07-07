"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph3D from "react-force-graph-3d";
import { Brain } from "lucide-react";

/**
 * MemoryGraph3D — interactive WebGL force-directed view of the MemPalace
 * knowledge graph, backed by the existing /v1/palace/graph?format=json endpoint.
 *
 * Nodes are colored by community, sized by relevance (access_count / memory_count),
 * and edges shaded by similarity weight. Drag to rotate, scroll to zoom, click a
 * node to focus its neighbourhood. This replaces the 2D D3 iframe for the Memory
 * Graph tab; the classic 2D page is still reachable via "open external".
 *
 * Must be loaded via next/dynamic({ ssr: false }) — ForceGraph3D touches WebGL.
 */

// Distinct, dark-bg-friendly hues cycled by community id.
const COMMUNITY_COLORS = [
  "#60a5fa", "#f472b6", "#34d399", "#fbbf24", "#a78bfa", "#22d3ee",
  "#fb923c", "#4ade80", "#f87171", "#c084fc", "#2dd4bf", "#e879f9",
];

interface RawNode {
  id: string;
  label?: string;
  community?: number;
  access_count?: number;
  memory_count?: number;
  memory_type?: string;
  entity_type?: string;
  domain?: string | null;
}
interface RawEdge {
  source: string;
  target: string;
  weight?: number;
}
interface GNode extends RawNode {
  name: string;
  val: number;
  color: string;
}

function communityColor(c: number | undefined): string {
  if (c == null) return "#94a3b8";
  return COMMUNITY_COLORS[((c % COMMUNITY_COLORS.length) + COMMUNITY_COLORS.length) % COMMUNITY_COLORS.length];
}

export function MemoryGraph3D({
  ownerId,
  reloadKey = 0,
  onLoaded,
}: {
  ownerId: string | null;
  reloadKey?: number;
  onLoaded?: () => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ w: 0, h: 0 });
  const [nodes, setNodes] = useState<GNode[]>([]);
  const [links, setLinks] = useState<RawEdge[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [message, setMessage] = useState<string>("");

  // Track container size for the canvas.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const update = () => setDims({ w: el.clientWidth, h: el.clientHeight });
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Fetch + normalize graph data.
  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    const params = new URLSearchParams({ mode: "auto", format: "json" });
    if (ownerId) params.set("owner_id", ownerId);

    fetch(`/api/backend/v1/palace/graph?${params.toString()}`)
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (cancelled) return;
        const g = data?.graph ?? {};
        const rawNodes: RawNode[] = g.nodes ?? [];
        const rawEdges: RawEdge[] = g.edges ?? g.links ?? [];
        if (!rawNodes.length) {
          setStatus("empty");
          setMessage(data?.message || "No memory graph yet — capture some memories first.");
          onLoaded?.();
          return;
        }
        const gnodes: GNode[] = rawNodes.map((n) => {
          const relevance = n.memory_count ?? n.access_count ?? 1;
          return {
            ...n,
            name: n.label || n.id,
            val: Math.max(1, relevance),
            color: communityColor(n.community),
          };
        });
        // Keep only edges whose endpoints exist (defensive).
        const ids = new Set(gnodes.map((n) => n.id));
        const gedges = rawEdges.filter((e) => ids.has(e.source) && ids.has(e.target));
        setNodes(gnodes);
        setLinks(gedges);
        setStatus("ready");
        onLoaded?.();
      })
      .catch((e) => {
        if (cancelled) return;
        setStatus("error");
        setMessage(String(e));
        onLoaded?.();
      });

    return () => {
      cancelled = true;
    };
  }, [ownerId, reloadKey, onLoaded]);

  const graphData = useMemo(() => ({ nodes, links }), [nodes, links]);

  return (
    <div ref={containerRef} className="relative flex-1 w-full overflow-hidden" style={{ background: "var(--chat-bg)" }}>
      {status === "ready" && dims.w > 0 && (
        <ForceGraph3D
          graphData={graphData}
          width={dims.w}
          height={dims.h}
          backgroundColor="rgba(0,0,0,0)"
          nodeVal={(n: GNode) => n.val}
          nodeColor={(n: GNode) => n.color}
          nodeRelSize={4}
          nodeOpacity={0.9}
          nodeLabel={(n: GNode) =>
            `<div style="max-width:280px;font:12px/1.4 system-ui;color:#e5e7eb;background:#111827;border:1px solid #374151;border-radius:6px;padding:6px 8px">
               <b>${escapeHtml(n.name)}</b>
               <div style="color:#9ca3af;margin-top:2px">${escapeHtml(n.entity_type || n.memory_type || "")}${
              n.community != null ? ` · community ${n.community}` : ""
            }</div>
             </div>`
          }
          linkColor={() => "rgba(148,163,184,0.28)"}
          linkWidth={(l: RawEdge) => Math.max(0.3, (l.weight ?? 0.3) * 1.5)}
          linkOpacity={0.35}
          enableNodeDrag={false}
          warmupTicks={40}
          cooldownTicks={120}
        />
      )}

      {status !== "ready" && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="flex flex-col items-center gap-2 text-center">
            <Brain size={24} className="text-[var(--chat-subtle)]" />
            {status === "loading" && (
              <p className="text-sm text-[var(--chat-muted)]">Building 3D memory graph…</p>
            )}
            {status === "empty" && (
              <>
                <p className="text-sm text-[var(--chat-text)]">No memory graph yet.</p>
                <p className="max-w-sm text-[12px] text-[var(--chat-muted)]">{message}</p>
              </>
            )}
            {status === "error" && (
              <>
                <p className="text-sm text-red-400">Failed to load memory graph.</p>
                <p className="max-w-sm text-[12px] text-[var(--chat-muted)]">{message}</p>
              </>
            )}
          </div>
        </div>
      )}

      {status === "ready" && (
        <div className="pointer-events-none absolute bottom-3 left-3 rounded-md border border-[var(--chat-border)] bg-black/40 px-2.5 py-1.5 text-[11px] text-[var(--chat-subtle)]">
          {nodes.length} nodes · {links.length} edges · colored by community
        </div>
      )}
    </div>
  );
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
