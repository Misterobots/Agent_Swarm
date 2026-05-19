// ui/src/types/goals.ts

export type GoalStatus = "active" | "complete" | "paused";
export type PlanStatus = "pending" | "in_progress" | "completed";
export type EvidenceType = "command_output" | "file_ref" | "test_result" | "note";

export interface Goal {
  id: string;
  threadId: string;
  ownerId: string;
  objective: string;
  status: GoalStatus;
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
  tokensUsed: number;
  timeUsedSeconds: number;
}

export interface GoalPlanStep {
  id: string;
  goalId: string;
  step: string;
  status: PlanStatus;
  ord: number;
}

export interface GoalEvidence {
  id: string;
  goalId: string;
  requirement: string;
  evidenceType: EvidenceType;
  evidenceRef: string;
  createdAt: string;
}

export interface GoalDetail extends Goal {
  steps: GoalPlanStep[];
  evidence: GoalEvidence[];
}
