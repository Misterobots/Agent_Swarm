"use client";

import { useState } from "react";
import { useTraces } from "@/lib/hooks/use-traces";
import { TraceTable } from "./trace-table";
import { TraceDetail } from "./trace-detail";
import { Search, RefreshCw } from "lucide-react";

export function TraceBrowser() {
  const { traces, loading, error, search, setSearch, refresh } = useTraces();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-[var(--chat-text)]">Swarm Observer</h1>
        <button
          onClick={refresh}
          disabled={loading}
          className="p-2 rounded-lg text-[var(--chat-muted)] hover:text-[var(--chat-accent)] hover:bg-[var(--chat-surface)] transition-colors disabled:opacity-50"
        >
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--chat-muted)]" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search traces by name..."
          className="w-full pl-9 pr-4 py-2 bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-lg text-sm text-[var(--chat-text)] placeholder:text-[var(--chat-muted)] focus:outline-none focus:border-[var(--chat-accent)]"
        />
      </div>

      {/* Error */}
      {error && (
        <div className="px-4 py-3 bg-red-900/20 border border-red-800/30 rounded-lg text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="border border-[var(--chat-border)] rounded-lg overflow-hidden">
        {loading && traces.length === 0 ? (
          <div className="text-center py-12 text-[var(--chat-muted)] text-sm">Loading traces...</div>
        ) : (
          <TraceTable
            traces={traces}
            selectedId={selectedId}
            onSelect={(id) => setSelectedId(id === selectedId ? null : id)}
          />
        )}

        {/* Detail panel */}
        {selectedId && (
          <TraceDetail traceId={selectedId} onClose={() => setSelectedId(null)} />
        )}
      </div>
    </div>
  );
}
