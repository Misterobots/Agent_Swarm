"use client";

import { useEffect, useCallback } from "react";
import { useSwarmStore } from "@/lib/stores/swarm-store";
import { SwarmPanelContent } from "@/components/swarm/swarm-drawer";
import type { SwarmTheaterPhase } from "@/lib/stores/swarm-store";

const CHANNEL = "hive-swarm";

/**
 * Standalone swarm panel page — opened as a detached popup window from the
 * desktop drawer's popout button.
 *
 * Receives live state via BroadcastChannel("hive-swarm") from the main tab.
 * Read-only: interactions (select worker etc.) are reflected locally only.
 */
export default function SwarmPopupPage() {
  const store = useSwarmStore();
  const { theaterPhase, phaseName, workers, latestCard, selectedWorkerId } = store;

  useEffect(() => {
    let channel: BroadcastChannel;
    try {
      channel = new BroadcastChannel(CHANNEL);
    } catch {
      return;
    }

    // Request immediate state from main tab
    channel.postMessage({ type: "request_state" });

    channel.onmessage = (ev: MessageEvent) => {
      const { type, payload } = ev.data ?? {};
      if ((type === "state_update" || type === "state_snapshot") && payload) {
        // Hydrate only the data fields (not functions)
        useSwarmStore.setState({
          active: payload.active,
          theaterPhase: payload.theaterPhase,
          phaseNum: payload.phaseNum,
          phaseName: payload.phaseName,
          workers: payload.workers,
          latestCard: payload.latestCard,
          badgeQueue: payload.badgeQueue ?? [],
          revealedWorkerIds: payload.revealedWorkerIds ?? [],
          phaseNameMap: payload.phaseNameMap ?? {},
          taskSummary: payload.taskSummary,
        });
      }
    };

    return () => channel.close();
  }, []);

  const handleCardDone = useCallback(() => {
    useSwarmStore.getState().dequeueBadge();
  }, []);

  const handleSelectWorker = useCallback((id: string | null) => {
    useSwarmStore.setState({ selectedWorkerId: id });
  }, []);

  const handlePhaseChange = useCallback((phase: SwarmTheaterPhase) => {
    useSwarmStore.setState({ theaterPhase: phase });
  }, []);

  return (
    <div className="flex flex-col h-screen bg-[var(--chat-bg)] overflow-hidden">
      {/* Minimal popup header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--chat-border)] flex-shrink-0 bg-[var(--chat-surface)]">
        <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        <span className="text-xs font-semibold text-[var(--chat-text)] opacity-80 tracking-wide uppercase">
          Agent Swarm — Live View
        </span>
        <span className="ml-auto text-[10px] text-[var(--chat-muted)] opacity-70">
          {workers.length} pioneer{workers.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Shared panel content */}
      <SwarmPanelContent
        theaterPhase={theaterPhase}
        phaseName={phaseName}
        workers={workers}
        latestCard={latestCard}
        selectedWorkerId={selectedWorkerId}
        onCardDone={handleCardDone}
        onSelectWorker={handleSelectWorker}
        onPhaseChange={handlePhaseChange}
      />
    </div>
  );
}
