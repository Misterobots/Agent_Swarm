import type { ContextProfile, ConversationExperience } from "@/types/chat";

export type ContextProfileSelection = ContextProfile | "auto";

/** Resolve the effective profile for display without changing request semantics. */
export function resolveContextProfile(
  selection: ContextProfileSelection,
  experience?: ConversationExperience,
  swarmMode = false,
): ContextProfile {
  if (selection !== "auto") return selection;
  if (swarmMode || experience === "code") return "project";
  return "chat";
}

/** Auto is intentionally omitted so the server derives its task default. */
export function requestContextProfile(
  selection: ContextProfileSelection,
): ContextProfile | undefined {
  return selection === "auto" ? undefined : selection;
}
