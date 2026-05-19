"use client";

import { useState, useEffect } from "react";
import { Key, CheckCircle2, XCircle, Loader2, Plus, Trash2 } from "lucide-react";

const API_BASE = "/api/backend";

interface ProviderInfo {
  label: string;
  models: Array<{ id: string; label: string; context: number }>;
}

interface ConnectedProvider {
  provider: string;
  label: string;
  connected_at: string | null;
}

interface ProviderCatalog {
  [key: string]: ProviderInfo;
}

interface ConnectFormData {
  provider: string;
  api_key: string;
  label: string;
}

export function ProviderKeysConnect() {
  const [catalog, setCatalog] = useState<ProviderCatalog>({});
  const [connected, setConnected] = useState<ConnectedProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<ConnectFormData>({
    provider: "",
    api_key: "",
    label: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  useEffect(() => {
    fetchData();
  }, []);

  async function fetchData() {
    setLoading(true);
    try {
      const [catalogRes, connectedRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/provider-keys/providers`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/v1/provider-keys/list`, { cache: "no-store" }),
      ]);
      
      if (catalogRes.ok) {
        const catalogData: ProviderCatalog = await catalogRes.json();
        setCatalog(catalogData);
      }
      
      if (connectedRes.ok) {
        const connectedData = await connectedRes.json();
        setConnected(connectedData.providers || []);
      }
    } catch (err) {
      console.error("[ProviderKeysConnect] fetchData error:", err);
      setErrorMsg("Failed to load provider data");
    } finally {
      setLoading(false);
    }
  }

  async function handleConnect() {
    if (!formData.provider || !formData.api_key) {
      setErrorMsg("Provider and API key are required");
      return;
    }

    setSubmitting(true);
    setErrorMsg("");
    setSuccessMsg("");

    try {
      const res = await fetch(`${API_BASE}/api/v1/provider-keys/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${res.status}`);
      }

      setSuccessMsg(`Connected ${formData.provider} successfully`);
      setShowForm(false);
      setFormData({ provider: "", api_key: "", label: "" });
      await fetchData();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to connect provider";
      console.error("[ProviderKeysConnect] handleConnect error:", err);
      setErrorMsg(msg);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDisconnect(provider: string) {
    if (!confirm(`Disconnect ${provider}? This will remove your stored API key.`)) {
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/v1/provider-keys/${provider}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      setSuccessMsg(`Disconnected ${provider}`);
      await fetchData();
    } catch (err) {
      console.error("[ProviderKeysConnect] handleDisconnect error:", err);
      setErrorMsg("Failed to disconnect provider");
    }
  }

  function isConnected(providerId: string): boolean {
    return connected.some((c) => c.provider === providerId);
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-[var(--chat-muted)]">
        <Loader2 size={14} className="animate-spin" />
        <span>Loading provider information…</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Success/Error Messages */}
      {successMsg && (
        <div className="flex items-center gap-2 text-sm text-green-500 bg-green-500/10 border border-green-500/20 rounded-md px-3 py-2">
          <CheckCircle2 size={14} />
          <span>{successMsg}</span>
        </div>
      )}
      {errorMsg && (
        <div className="flex items-center gap-2 text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-md px-3 py-2">
          <XCircle size={14} />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Connected Providers */}
      {connected.length > 0 && (
        <div className="space-y-2">
          {connected.map((conn) => {
            const providerInfo = catalog[conn.provider];
            return (
              <div
                key={conn.provider}
                className="flex items-center justify-between bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-lg px-3 py-2"
              >
                <div className="flex items-center gap-2 text-sm">
                  <CheckCircle2 size={14} className="text-green-500" />
                  <Key size={13} className="text-[var(--chat-text)]" />
                  <span className="text-[var(--chat-text)] font-medium">
                    {providerInfo?.label || conn.provider}
                  </span>
                  {conn.label && (
                    <span className="text-xs text-[var(--chat-muted)]">({conn.label})</span>
                  )}
                </div>
                <button
                  onClick={() => handleDisconnect(conn.provider)}
                  className="text-xs text-[var(--chat-muted)] hover:text-red-400 transition-colors flex items-center gap-1"
                >
                  <Trash2 size={12} />
                  Disconnect
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Add Provider Button/Form */}
      {!showForm && (
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-3 py-2 bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-lg text-sm text-[var(--chat-text)] hover:border-[var(--chat-accent)]/60 hover:bg-[var(--chat-surface)] transition-colors"
        >
          <Plus size={14} />
          Add Provider API Key
        </button>
      )}

      {/* Connection Form */}
      {showForm && (
        <div className="surface p-4 space-y-3">
          <div>
            <label className="text-xs text-[var(--chat-muted)] mb-1.5 block">Provider</label>
            <select
              value={formData.provider}
              onChange={(e) => setFormData({ ...formData, provider: e.target.value })}
              className="input-field w-full text-sm"
            >
              <option value="">Select a provider…</option>
              {Object.entries(catalog).map(([id, info]) => (
                <option key={id} value={id} disabled={isConnected(id)}>
                  {info.label} {isConnected(id) ? "(connected)" : ""}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs text-[var(--chat-muted)] mb-1.5 block">API Key</label>
            <input
              type="password"
              value={formData.api_key}
              onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
              placeholder="sk-ant-… or AI…"
              className="input-field w-full text-sm"
            />
          </div>

          <div>
            <label className="text-xs text-[var(--chat-muted)] mb-1.5 block">
              Label (optional)
            </label>
            <input
              type="text"
              value={formData.label}
              onChange={(e) => setFormData({ ...formData, label: e.target.value })}
              placeholder="My key, Work account, etc."
              className="input-field w-full text-sm"
            />
          </div>

          <div className="flex gap-2 pt-1">
            <button
              onClick={handleConnect}
              disabled={submitting || !formData.provider || !formData.api_key}
              className="btn-primary flex-1 inline-flex items-center justify-center gap-2 px-4 py-2 text-sm rounded-md"
            >
              {submitting ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  <span>Connecting…</span>
                </>
              ) : (
                <>
                  <Key size={14} />
                  <span>Connect</span>
                </>
              )}
            </button>
            <button
              onClick={() => {
                setShowForm(false);
                setFormData({ provider: "", api_key: "", label: "" });
                setErrorMsg("");
              }}
              disabled={submitting}
              className="btn-secondary px-4 py-2 text-sm rounded-md"
            >
              Cancel
            </button>
          </div>

          {/* Provider Info */}
          {formData.provider && catalog[formData.provider] && (
            <div className="pt-3 border-t border-[var(--chat-border)]">
              <p className="text-xs text-[var(--chat-subtle)] uppercase tracking-wide font-medium mb-2">
                Available models
              </p>
              <div className="space-y-1">
                {catalog[formData.provider].models.map((model) => (
                  <div
                    key={model.id}
                    className="text-xs text-[var(--chat-text)] flex items-center justify-between"
                  >
                    <span>{model.label}</span>
                    <span className="text-[var(--chat-muted)] tabular-nums">
                      {(model.context / 1000).toFixed(0)}k context
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Help Text */}
      {!showForm && connected.length === 0 && (
        <p className="text-xs text-[var(--chat-muted)]">
          No provider API keys connected. Add a key to access premium models like Claude and Gemini.
        </p>
      )}
    </div>
  );
}
