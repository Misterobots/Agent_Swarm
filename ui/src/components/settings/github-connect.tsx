"use client";

import { useState, useEffect, useRef } from "react";
import { Github, CheckCircle2, XCircle, Loader2, ExternalLink } from "lucide-react";

const API_BASE = "/api/backend";

interface GitHubStatus {
  connected: boolean;
  username: string | null;
}

interface DeviceAuthResponse {
  device_code: string;
  user_code: string;
  verification_uri: string;
  expires_in: number;
  interval: number;
}

type FlowState = "idle" | "pending" | "polling" | "connected" | "error";

export function GitHubConnect() {
  const [status, setStatus] = useState<GitHubStatus>({ connected: false, username: null });
  const [flowState, setFlowState] = useState<FlowState>("idle");
  const [userCode, setUserCode] = useState("");
  const [verificationUri, setVerificationUri] = useState("");
  const [deviceCode, setDeviceCode] = useState("");
  const [pollInterval, setPollInterval] = useState(5);
  const [errorMsg, setErrorMsg] = useState("");
  const [loading, setLoading] = useState(true);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    fetchStatus();
  }, []);

  async function fetchStatus() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/github/status`);
      if (res.ok) {
        const data: GitHubStatus = await res.json();
        setStatus(data);
        if (data.connected) setFlowState("connected");
      }
    } catch (err) {
      console.error("[GitHubConnect] fetchStatus error:", err);
    } finally {
      setLoading(false);
    }
  }

  async function startDeviceFlow() {
    setFlowState("pending");
    setErrorMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/v1/github/device-authorize`, {
        method: "POST",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${res.status}`);
      }
      const data: DeviceAuthResponse = await res.json();
      setUserCode(data.user_code);
      setVerificationUri(data.verification_uri);
      setDeviceCode(data.device_code);
      setPollInterval(data.interval || 5);
      setFlowState("polling");
      startPolling(data.device_code, data.interval || 5);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to start device flow";
      console.error("[GitHubConnect] startDeviceFlow error:", err);
      setErrorMsg(msg);
      setFlowState("error");
    }
  }

  function startPolling(code: string, interval: number) {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(() => pollToken(code), interval * 1000);
  }

  async function pollToken(code: string) {
    try {
      const res = await fetch(`${API_BASE}/api/v1/github/device-poll`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device_code: code }),
      });
      const data = await res.json();
      if (data.status === "authorized") {
        stopPolling();
        setStatus({ connected: true, username: data.username });
        setFlowState("connected");
      } else if (data.status === "pending") {
        // still waiting — keep polling
      } else if (data.status === "error" || !res.ok) {
        stopPolling();
        const msg = data.message || data.detail || "Authorization failed.";
        setErrorMsg(msg.includes("access_denied") ? "Access denied by user." : msg.includes("expired") ? "Device code expired. Please try again." : msg);
        setFlowState("error");
      }
    } catch (err) {
      console.error("[GitHubConnect] pollToken error:", err);
    }
  }

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  function cancelFlow() {
    stopPolling();
    setFlowState("idle");
    setUserCode("");
    setDeviceCode("");
    setVerificationUri("");
  }

  async function disconnect() {
    try {
      await fetch(`${API_BASE}/api/v1/github/disconnect`, { method: "DELETE" });
      setStatus({ connected: false, username: null });
      setFlowState("idle");
    } catch (err) {
      console.error("[GitHubConnect] disconnect error:", err);
    }
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => stopPolling();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-[var(--chat-muted)]">
        <Loader2 size={14} className="animate-spin" />
        <span>Checking GitHub connection…</span>
      </div>
    );
  }

  if (flowState === "connected") {
    return (
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm">
          <CheckCircle2 size={16} className="text-green-500" />
          <Github size={15} className="text-[var(--chat-text)]" />
          <span className="text-[var(--chat-text)]">Connected as</span>
          <span className="font-medium text-[var(--chat-text)]">@{status.username}</span>
        </div>
        <button
          onClick={disconnect}
          className="text-xs text-[var(--chat-muted)] hover:text-red-400 transition-colors"
        >
          Disconnect
        </button>
      </div>
    );
  }

  if (flowState === "polling") {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-sm text-[var(--chat-muted)]">
          <Loader2 size={14} className="animate-spin" />
          <span>Waiting for GitHub authorization…</span>
        </div>
        <div className="bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-lg px-4 py-3 space-y-2">
          <p className="text-xs text-[var(--chat-muted)]">Visit GitHub and enter this code:</p>
          <div className="flex items-center justify-between">
            <span className="font-mono text-xl font-bold tracking-widest text-[var(--chat-accent)]">
              {userCode}
            </span>
            <a
              href={verificationUri}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-xs text-[var(--chat-accent)] hover:underline"
            >
              Open GitHub <ExternalLink size={11} />
            </a>
          </div>
        </div>
        <button
          onClick={cancelFlow}
          className="text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors"
        >
          Cancel
        </button>
      </div>
    );
  }

  if (flowState === "error") {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-sm text-red-400">
          <XCircle size={14} />
          <span>{errorMsg}</span>
        </div>
        <button
          onClick={() => setFlowState("idle")}
          className="text-xs text-[var(--chat-accent)] hover:underline"
        >
          Try again
        </button>
      </div>
    );
  }

  // idle
  return (
    <button
      onClick={startDeviceFlow}
      disabled={flowState === "pending"}
      className="flex items-center gap-2 px-3 py-2 bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-lg text-sm text-[var(--chat-text)] hover:border-[var(--chat-accent)]/60 hover:bg-[var(--chat-surface)] transition-colors disabled:opacity-50"
    >
      {flowState === "pending" ? (
        <Loader2 size={14} className="animate-spin" />
      ) : (
        <Github size={14} />
      )}
      Connect GitHub Models
    </button>
  );
}
