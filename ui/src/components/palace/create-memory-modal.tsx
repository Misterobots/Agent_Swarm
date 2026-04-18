"use client";

import { useState, useCallback } from "react";
import { X } from "lucide-react";
import { createMemory } from "@/lib/api/palace";
import { usePalaceStore } from "@/lib/stores/palace-store";

const MEMORY_TYPES = ["semantic", "episodic", "procedural", "preference", "discovery"];
const DOMAINS = ["general", "coding", "visual", "architecture", "preferences"];

interface CreateMemoryModalProps {
  onClose: () => void;
}

export function CreateMemoryModal({ onClose }: CreateMemoryModalProps) {
  const refreshRoom = usePalaceStore((s) => s.refreshRoom);
  const adminViewingOwner = usePalaceStore((s) => s.adminViewingOwner);

  const [content, setContent] = useState("");
  const [memoryType, setMemoryType] = useState("semantic");
  const [domain, setDomain] = useState("general");
  const [ownerId, setOwnerId] = useState(adminViewingOwner || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleCreate = useCallback(async () => {
    if (!content.trim()) {
      setError("Content is required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await createMemory({
        content: content.trim(),
        memory_type: memoryType,
        domain,
        owner_id: ownerId || undefined,
      });
      await refreshRoom();
      onClose();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }, [content, memoryType, domain, ownerId, refreshRoom, onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      {/* Modal */}
      <div
        className="relative w-full max-w-md rounded-xl overflow-hidden"
        style={{
          background: "var(--chat-surface)",
          border: "1px solid var(--chat-border)",
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-3"
          style={{ borderBottom: "1px solid var(--chat-border)" }}
        >
          <span className="text-sm font-medium" style={{ color: "var(--chat-text)" }}>
            Create Memory
          </span>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-[var(--chat-soft)]"
            style={{ color: "var(--chat-muted)" }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Form */}
        <div className="p-5 space-y-4">
          {/* Content */}
          <div>
            <label className="block text-xs mb-1" style={{ color: "var(--chat-muted)" }}>
              Content
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={4}
              className="w-full p-2.5 rounded-lg text-sm resize-none outline-none"
              style={{
                background: "var(--chat-panel)",
                border: "1px solid var(--chat-border)",
                color: "var(--chat-text)",
              }}
              placeholder="Memory content…"
              autoFocus
            />
          </div>

          {/* Type + Domain */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs mb-1" style={{ color: "var(--chat-muted)" }}>
                Type
              </label>
              <select
                value={memoryType}
                onChange={(e) => setMemoryType(e.target.value)}
                className="w-full p-2 rounded-lg text-sm outline-none"
                style={{
                  background: "var(--chat-panel)",
                  border: "1px solid var(--chat-border)",
                  color: "var(--chat-text)",
                }}
              >
                {MEMORY_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs mb-1" style={{ color: "var(--chat-muted)" }}>
                Domain
              </label>
              <select
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                className="w-full p-2 rounded-lg text-sm outline-none"
                style={{
                  background: "var(--chat-panel)",
                  border: "1px solid var(--chat-border)",
                  color: "var(--chat-text)",
                }}
              >
                {DOMAINS.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Owner ID */}
          <div>
            <label className="block text-xs mb-1" style={{ color: "var(--chat-muted)" }}>
              Owner ID (optional)
            </label>
            <input
              value={ownerId}
              onChange={(e) => setOwnerId(e.target.value)}
              className="w-full p-2 rounded-lg text-sm outline-none"
              style={{
                background: "var(--chat-panel)",
                border: "1px solid var(--chat-border)",
                color: "var(--chat-text)",
              }}
              placeholder="Leave blank for unowned"
            />
          </div>

          {error && (
            <div className="text-xs" style={{ color: "var(--chat-accent-2)" }}>
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-end gap-2 px-5 py-3"
          style={{ borderTop: "1px solid var(--chat-border)" }}
        >
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded-lg text-xs"
            style={{
              background: "var(--chat-panel)",
              color: "var(--chat-muted)",
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={saving}
            className="px-4 py-1.5 rounded-lg text-xs font-medium"
            style={{
              background: "var(--chat-accent)",
              color: "var(--chat-bg)",
              opacity: saving ? 0.5 : 1,
            }}
          >
            {saving ? "Creating…" : "Create Memory"}
          </button>
        </div>
      </div>
    </div>
  );
}
