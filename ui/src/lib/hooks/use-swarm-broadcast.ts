"use client";

import { useEffect } from "react";
import { useSwarmStore } from "@/lib/stores/swarm-store";

const CHANNEL = "hive-swarm";

/**
 * Bridges the swarm Zustand store to a BroadcastChannel so that detached
 * popup windows (e.g. /swarm) can receive live state updates.
 *
 * Call this once at the chat-view or layout level. It sets up:
 *   - A subscription that posts every store change to the channel
 *   - A message handler that responds to "request_state" with current state
 */
export function useSwarmBroadcast() {
  useEffect(() => {
    let channel: BroadcastChannel;
    try {
      channel = new BroadcastChannel(CHANNEL);
    } catch {
      // BroadcastChannel not supported (e.g. Safari private mode)
      return;
    }

    // Respond to popout windows requesting an immediate state snapshot
    channel.onmessage = (ev: MessageEvent) => {
      if (ev.data?.type === "request_state") {
        const state = useSwarmStore.getState();
        channel.postMessage({ type: "state_snapshot", payload: state });
      }
    };

    // Publish every store change
    const unsubscribe = useSwarmStore.subscribe((state) => {
      channel.postMessage({ type: "state_update", payload: state });
    });

    return () => {
      unsubscribe();
      channel.close();
    };
  }, []);
}
