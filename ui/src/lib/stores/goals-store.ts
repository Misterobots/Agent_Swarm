// ui/src/lib/stores/goals-store.ts
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Goal, GoalPlanStep, GoalEvidence, GoalStatus, PlanStatus, EvidenceType } from "@/types/goals";

const API = "/api/backend/v1/goals";

async function apiFetch(path: string, options?: RequestInit) {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`Goals API error ${res.status}`);
  return res.json();
}

interface GoalsState {
  // Current active goal for the thread shown in chat
  activeGoal: Goal | null;
  steps: GoalPlanStep[];
  evidence: GoalEvidence[];

  // Panel visibility
  panelOpen: boolean;
  setPanelOpen: (open: boolean) => void;

  // Loading
  loading: boolean;
  error: string | null;

  // Actions
  ensureGoal: (threadId: string, objective: string) => Promise<void>;
  refreshGoal: (goalId: string) => Promise<void>;
  completeGoal: (goalId: string) => Promise<void>;
  pauseGoal: (goalId: string) => Promise<void>;

  updateStep: (goalId: string, stepId: string, status: PlanStatus) => Promise<void>;
  setPlan: (goalId: string, steps: Array<{ step: string; status?: PlanStatus; ord: number }>) => Promise<void>;

  addEvidence: (goalId: string, requirement: string, evidenceType: EvidenceType, evidenceRef: string) => Promise<void>;

  updateUsage: (goalId: string, deltaTokens: number, deltaSeconds: number) => Promise<void>;

  clearGoal: () => void;
}

export const useGoalsStore = create<GoalsState>()(
  persist(
    (set, get) => ({
      activeGoal: null,
      steps: [],
      evidence: [],
      panelOpen: false,
      loading: false,
      error: null,

      setPanelOpen: (open) => set({ panelOpen: open }),

      clearGoal: () => set({ activeGoal: null, steps: [], evidence: [], panelOpen: false }),

      ensureGoal: async (threadId, objective) => {
        set({ loading: true, error: null });
        try {
          const data = await apiFetch("/ensure", {
            method: "POST",
            body: JSON.stringify({ thread_id: threadId, objective }),
          });
          const goal = snakeToCamel(data.goal) as Goal;
          set({ activeGoal: goal, loading: false });
          // Auto-open panel when a goal is created/found
          set({ panelOpen: true });
          // Also fetch steps/evidence
          await get().refreshGoal(goal.id);
        } catch (e) {
          set({ loading: false, error: String(e) });
        }
      },

      refreshGoal: async (goalId) => {
        try {
          const data = await apiFetch(`/${goalId}`);
          const goal = snakeToCamel(data.goal) as Goal;
          const steps = (data.steps as object[]).map(snakeToCamel) as GoalPlanStep[];
          const evidence = (data.evidence as object[]).map(snakeToCamel) as GoalEvidence[];
          set({ activeGoal: goal, steps, evidence });
        } catch (e) {
          set({ error: String(e) });
        }
      },

      completeGoal: async (goalId) => {
        await apiFetch(`/${goalId}/complete`, { method: "POST" });
        await get().refreshGoal(goalId);
      },

      pauseGoal: async (goalId) => {
        await apiFetch(`/${goalId}/pause`, { method: "POST" });
        await get().refreshGoal(goalId);
      },

      updateStep: async (goalId, stepId, status) => {
        await apiFetch(`/${goalId}/plan/${stepId}`, {
          method: "PATCH",
          body: JSON.stringify({ status }),
        });
        await get().refreshGoal(goalId);
      },

      setPlan: async (goalId, steps) => {
        await apiFetch(`/${goalId}/plan`, {
          method: "PUT",
          body: JSON.stringify({ steps }),
        });
        await get().refreshGoal(goalId);
      },

      addEvidence: async (goalId, requirement, evidenceType, evidenceRef) => {
        await apiFetch(`/${goalId}/evidence`, {
          method: "POST",
          body: JSON.stringify({
            requirement,
            evidence_type: evidenceType,
            evidence_ref: evidenceRef,
          }),
        });
        await get().refreshGoal(goalId);
      },

      updateUsage: async (goalId, deltaTokens, deltaSeconds) => {
        await apiFetch(`/${goalId}/usage`, {
          method: "POST",
          body: JSON.stringify({ delta_tokens: deltaTokens, delta_seconds: deltaSeconds }),
        });
      },
    }),
    {
      name: "goals-store",
      // Only persist panel preference — goal state comes from server
      partialize: (s) => ({ panelOpen: s.panelOpen }),
    },
  ),
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function snakeToCamel(obj: object): object {
  if (Array.isArray(obj)) return obj.map(snakeToCamel);
  if (obj === null || typeof obj !== "object") return obj;
  return Object.fromEntries(
    Object.entries(obj).map(([k, v]) => [
      k.replace(/_([a-z])/g, (_, c) => c.toUpperCase()),
      v && typeof v === "object" ? snakeToCamel(v as object) : v,
    ]),
  );
}
