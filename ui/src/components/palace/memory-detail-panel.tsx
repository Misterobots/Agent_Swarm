"use client";

import { useCallback, useState, useEffect } from "react";
import { X, Edit3, Trash2, Save, Clock, Plus } from "lucide-react";
import { usePalaceStore } from "@/lib/stores/palace-store";
import { usePalaceColors } from "@/lib/palace/theme-materials";
import { useAccess } from "@/lib/hooks/use-access";
import { editMemory, deleteMemory } from "@/lib/api/palace";
import { AuditBadge } from "./audit-badge";
import { CreateMemoryModal } from "./create-memory-modal";

export function MemoryDetailPanel() {
  const selectedMemory = usePalaceStore((s) => s.selectedMemory);
  const selectMemory = usePalaceStore((s) => s.selectMemory);
  const refreshRoom = usePalaceStore((s) => s.refreshRoom);
  const { isAdmin, username } = useAccess();

  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const colors = usePalaceColors();

  // Determine if user can modify this memory
  const isOwner = selectedMemory?.owner_id === username;
  const canEdit = isOwner || isAdmin;
  const canDelete = isOwner || isAdmin;
  const canCreate = isAdmin;

  useEffect(() => {
    if (selectedMemory) {
      setEditContent(selectedMemory.content);
      setEditing(false);
    }
  }, [selectedMemory]);

  const handleSave = useCallback(async () => {
    if (!selectedMemory) return;
    setSaving(true);
    try {
      await editMemory(
        selectedMemory.id,
        { content: editContent },
        username || "anonymous",
        isAdmin ? "admin" : "user",
      );
      setEditing(false);
      await refreshRoom();
      // Refresh selected memory
      selectMemory({ ...selectedMemory, content: editContent });
    } catch (err) {
      console.error("Failed to save memory:", err);
    } finally {
      setSaving(false);
    }
  }, [selectedMemory, editContent, username, isAdmin, refreshRoom, selectMemory]);

  const handleDelete = useCallback(async () => {
    if (!selectedMemory || !confirm("Delete this memory permanently?")) return;
    setDeleting(true);
    try {
      await deleteMemory(selectedMemory.id);
      selectMemory(null);
      await refreshRoom();
    } catch (err) {
      console.error("Failed to delete memory:", err);
    } finally {
      setDeleting(false);
    }
  }, [selectedMemory, selectMemory, refreshRoom]);

  if (!selectedMemory) return null;

  const meta = selectedMemory.metadata || {};

  // owner_id was historically stored as an Authentik UID hash (64 hex chars).
  // Newer records use the human-readable username. Truncate legacy hashes so the
  // panel doesn't display a wall of hex.
  const displaySource = (() => {
    const v = selectedMemory.owner_id;
    if (!v) return null;
    if (v.length > 32 && /^[0-9a-f]+$/i.test(v)) return v.slice(0, 8) + "…";
    return v;
  })();

  return (
    <>
      {/* Slide-in panel */}
      <div
        className="absolute right-0 top-0 bottom-0 w-96 max-w-full z-20 flex flex-col overflow-hidden"
        style={{
          background: `rgba(var(--chat-surface-rgb, 30, 30, 30), ${colors.isLight ? 0.8 : 0.7})`,
          backdropFilter: "blur(20px) saturate(1.4)",
          WebkitBackdropFilter: "blur(20px) saturate(1.4)",
          borderLeft: `1px solid rgba(var(--chat-border-rgb, 60, 60, 60), ${colors.isLight ? 0.35 : 0.25})`,
          boxShadow: colors.isLight ? "-6px 0 24px rgba(0,0,0,0.08)" : "-8px 0 32px rgba(0,0,0,0.2)",
          animation: "slideInRight 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-3 shrink-0"
          style={{ borderBottom: "1px solid var(--chat-border)" }}
        >
          <div className="flex items-center gap-2">
            <span
              className="text-xs font-medium px-2 py-0.5 rounded"
              style={{
                background: "var(--chat-accent)",
                color: "var(--chat-bg)",
              }}
            >
              {selectedMemory.memory_type}
            </span>
            <span className="text-xs" style={{ color: "var(--chat-muted)" }}>
              {selectedMemory.domain}
            </span>
          </div>
          <button
            onClick={() => selectMemory(null)}
            className="p-1 rounded hover:bg-[var(--chat-soft)] transition-colors"
            style={{ color: "var(--chat-muted)" }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {editing ? (
            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              className="w-full h-40 p-3 rounded-lg text-sm resize-none outline-none"
              style={{
                background: "var(--chat-panel)",
                border: "1px solid var(--chat-border)",
                color: "var(--chat-text)",
              }}
              autoFocus
            />
          ) : (
            <div className="text-sm leading-relaxed" style={{ color: "var(--chat-text)" }}>
              {selectedMemory.content}
            </div>
          )}

          {/* Metadata grid */}
          <div
            className="grid grid-cols-2 gap-2 text-xs p-3 rounded-lg"
            style={{ background: "var(--chat-panel)" }}
          >
            {selectedMemory.agent_id && (
              <>
                <span style={{ color: "var(--chat-muted)" }}>Agent</span>
                <span style={{ color: "var(--chat-text)" }}>{selectedMemory.agent_id}</span>
              </>
            )}
            {displaySource && (
              <>
                <span style={{ color: "var(--chat-muted)" }}>Source</span>
                <span style={{ color: "var(--chat-text)" }}>{displaySource}</span>
              </>
            )}
            <span style={{ color: "var(--chat-muted)" }}>Created</span>
            <span style={{ color: "var(--chat-text)" }}>
              {new Date(selectedMemory.created_at).toLocaleString()}
            </span>
            <span style={{ color: "var(--chat-muted)" }}>Accessed</span>
            <span style={{ color: "var(--chat-text)" }}>{selectedMemory.access_count}×</span>
            {selectedMemory.wing && (
              <>
                <span style={{ color: "var(--chat-muted)" }}>Wing</span>
                <span style={{ color: "var(--chat-text)" }}>{selectedMemory.wing}</span>
              </>
            )}
            {selectedMemory.score !== null && selectedMemory.score !== undefined && (
              <>
                <span style={{ color: "var(--chat-muted)" }}>Relevance</span>
                <span style={{ color: "var(--chat-text)" }}>
                  {(selectedMemory.score * 100).toFixed(1)}%
                </span>
              </>
            )}
          </div>

          {/* Audit badge */}
          <AuditBadge memoryId={selectedMemory.id} />
        </div>

        {/* Actions footer */}
        <div
          className="flex items-center gap-2 px-4 py-3 shrink-0"
          style={{ borderTop: "1px solid var(--chat-border)" }}
        >
          {editing ? (
            <>
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                style={{
                  background: "var(--chat-accent)",
                  color: "var(--chat-bg)",
                  opacity: saving ? 0.5 : 1,
                }}
              >
                <Save size={12} /> {saving ? "Saving…" : "Save"}
              </button>
              <button
                onClick={() => {
                  setEditing(false);
                  setEditContent(selectedMemory.content);
                }}
                className="px-3 py-1.5 rounded-lg text-xs transition-colors"
                style={{
                  background: "var(--chat-panel)",
                  color: "var(--chat-muted)",
                }}
              >
                Cancel
              </button>
            </>
          ) : (
            <>
              {canEdit && (
                <button
                  onClick={() => setEditing(true)}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors hover:brightness-110"
                  style={{
                    background: "var(--chat-panel)",
                    color: "var(--chat-text)",
                    border: "1px solid var(--chat-border)",
                  }}
                >
                  <Edit3 size={12} /> Edit
                </button>
              )}
              {canDelete && (
                <button
                  onClick={handleDelete}
                  disabled={deleting}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                  style={{
                    background: "transparent",
                    color: "var(--chat-accent-2)",
                    border: "1px solid var(--chat-accent-2)",
                    opacity: deleting ? 0.5 : 1,
                  }}
                >
                  <Trash2 size={12} /> {deleting ? "Deleting…" : "Delete"}
                </button>
              )}
              {canCreate && (
                <button
                  onClick={() => setShowCreate(true)}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium ml-auto transition-colors"
                  style={{
                    background: "var(--chat-accent)",
                    color: "var(--chat-bg)",
                  }}
                >
                  <Plus size={12} /> New
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Create modal */}
      {showCreate && <CreateMemoryModal onClose={() => setShowCreate(false)} />}

      {/* Slide-in animation */}
      <style jsx global>{`
        @keyframes slideInRight {
          from {
            transform: translateX(100%);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
      `}</style>
    </>
  );
}
