"use client";

import { useEffect, useRef, useCallback } from "react";
import { useDevEditorStore } from "@/lib/stores/dev-editor-store";
import { useDevPanelStore } from "@/lib/stores/dev-panel-store";
import { useDevProjectStore } from "@/lib/stores/dev-project-store";

const IDENTITY_KEY = "memex-dev-identity";
const SESSION_ID_KEY = "memex-dev-session-id";
const API_SESSIONS = "/api/backend/v1/dev/sessions";
const API_ME = "/api/auth/me";

export function useDevSessionSync() {
  const sessionIdRef = useRef<string | null>(null);
  const pendingSaveRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Read current state for saving
  const { activeFile } = useDevEditorStore();
  const { viewMode, selectedNode } = useDevPanelStore();
  const { currentProjectId } = useDevProjectStore();

  // Setters for hydration
  const setActiveFile = useDevEditorStore((s) => s.setActiveFile);
  const setViewMode = useDevPanelStore((s) => s.setViewMode);
  const setSelectedNode = useDevPanelStore((s) => s.setSelectedNode);
  const setCurrentProjectId = useDevProjectStore((s) => s.setCurrentProjectId);

  // On mount: check identity, hydrate from server
  useEffect(() => {
    async function syncOnMount() {
      try {
        // 1. Get current user
        const meRes = await fetch(API_ME);
        if (!meRes.ok) return;
        const { username } = await meRes.json();
        if (!username) return;

        // 2. Identity change check
        let storedIdentity: string | null = null;
        try { storedIdentity = localStorage.getItem(IDENTITY_KEY); } catch { /* SSR / private mode */ }
        if (storedIdentity && storedIdentity !== username) {
          // Different user — clear session id so we create a fresh one
          try { localStorage.removeItem(SESSION_ID_KEY); } catch { /* best-effort */ }
        }
        try { localStorage.setItem(IDENTITY_KEY, username); } catch { /* best-effort */ }

        // 3. Try to restore last session id
        let storedSessionId: string | null = null;
        try { storedSessionId = localStorage.getItem(SESSION_ID_KEY); } catch { /* best-effort */ }

        // 4. Fetch sessions from server
        const sessionsRes = await fetch(API_SESSIONS);
        if (!sessionsRes.ok) return;
        const { sessions } = await sessionsRes.json();

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const session = sessions?.find((s: any) => s.id === storedSessionId)
          ?? sessions?.[0]; // fall back to most recent

        if (session) {
          // Hydrate store from server session
          sessionIdRef.current = session.id;
          try { localStorage.setItem(SESSION_ID_KEY, session.id); } catch { /* best-effort */ }
          if (session.active_file) setActiveFile(session.active_file);
          if (session.view_mode) setViewMode(session.view_mode);
          if (session.selected_node) setSelectedNode(session.selected_node);
          if (session.project_id) setCurrentProjectId(session.project_id);
        } else {
          // No session yet — create one
          const { activeFile: af } = useDevEditorStore.getState();
          const { viewMode: vm, selectedNode: sn } = useDevPanelStore.getState();
          const { currentProjectId: pid } = useDevProjectStore.getState();
          const createRes = await fetch(API_SESSIONS, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              active_file: af || null,
              view_mode: vm,
              selected_node: sn,
              project_id: pid || null,
            }),
          });
          if (createRes.ok) {
            const created = await createRes.json();
            sessionIdRef.current = created.id;
            try { localStorage.setItem(SESSION_ID_KEY, created.id); } catch { /* best-effort */ }
          }
        }
      } catch {
        // Network unavailable — stay with local state
      }
    }

    void syncOnMount();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Debounced save: fire after 1s of no changes
  const scheduleSave = useCallback(() => {
    if (!sessionIdRef.current) return;
    if (pendingSaveRef.current) clearTimeout(pendingSaveRef.current);
    pendingSaveRef.current = setTimeout(async () => {
      const { activeFile: af } = useDevEditorStore.getState();
      const { viewMode: vm, selectedNode: sn } = useDevPanelStore.getState();
      const { currentProjectId: pid } = useDevProjectStore.getState();
      try {
        await fetch(`${API_SESSIONS}/${sessionIdRef.current}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            active_file: af || null,
            view_mode: vm,
            selected_node: sn,
            project_id: pid || null,
          }),
        });
      } catch { /* best-effort */ }
    }, 1000);
  }, []);

  // Watch key state fields and schedule save on change
  useEffect(() => {
    scheduleSave();
  }, [activeFile, viewMode, selectedNode, currentProjectId, scheduleSave]);

  return { sessionId: sessionIdRef.current };
}
