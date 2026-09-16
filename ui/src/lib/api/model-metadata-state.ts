import type { ModelMetadata, StreamMode, TurnMetadata } from "../../types/chat";

export function resetTurnMetadata(): null {
  return null;
}

export function mergeModelMetadata(
  previous: TurnMetadata | null,
  metadata: ModelMetadata,
  turnId: string,
  streamModes: StreamMode[],
): TurnMetadata {
  return {
    turnId: previous?.turnId || turnId,
    agentName: previous?.agentName,
    streamModes,
    toolsInvoked: previous?.toolsInvoked || [],
    continuable: previous?.continuable ?? true,
    inContextTokens: previous?.inContextTokens,
    resumeToken: previous?.resumeToken,
    traceId: previous?.traceId,
    requestedModel: metadata.requestedModel ?? previous?.requestedModel,
    actualModel: metadata.actualModel ?? previous?.actualModel,
    provider: metadata.provider ?? previous?.provider,
    fallback: metadata.fallback ?? previous?.fallback,
    contextProfile: metadata.contextProfile ?? previous?.contextProfile,
    effectiveContextTokens: metadata.effectiveContextTokens ?? previous?.effectiveContextTokens,
  };
}
