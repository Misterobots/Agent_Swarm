"use client";

import { useState, useEffect } from "react";
import { Users, Save, RefreshCw, AlertCircle } from "lucide-react";

const API_BASE = "/api/backend";

interface RoleModel {
  role: string;
  role_label: string;
  model: string;
  description: string;
}

interface AvailableModel {
  name: string;
  size: number;
  modified_at: string;
}

const ROLES: RoleModel[] = [
  {
    role: "coordinator",
    role_label: "Coordinator (Memex)",
    model: "",
    description: "Task decomposition, planning, and orchestration",
  },
  {
    role: "architect",
    role_label: "Architect",
    model: "",
    description: "System design and architecture planning",
  },
  {
    role: "coder",
    role_label: "Coder",
    model: "",
    description: "Code implementation, file editing, debugging",
  },
  {
    role: "devops",
    role_label: "DevOps",
    model: "",
    description: "Infrastructure, Docker, bash scripts, deployments",
  },
  {
    role: "researcher",
    role_label: "Researcher",
    model: "",
    description: "Codebase investigation, context gathering",
  },
  {
    role: "analyst",
    role_label: "Analyst",
    model: "",
    description: "Data analysis, providing insights",
  },
  {
    role: "verifier",
    role_label: "Verifier",
    model: "",
    description: "Code review, validation, quality checks",
  },
];

const PRESET_PROFILES = [
  {
    id: "all-local",
    label: "All Local (No API costs)",
    config: {
      coordinator: "qwen3:14b",
      architect: "qwen2.5-coder:14b",
      coder: "qwen2.5-coder:14b",
      devops: "qwen3:8b",
      researcher: "llama3.2:3b",
      analyst: "qwen3:8b",
      verifier: "qwen3:8b",
    },
  },
  {
    id: "hybrid",
    label: "Hybrid (Local + Claude)",
    config: {
      coordinator: "qwen3:14b",
      architect: "qwen2.5-coder:14b",
      coder: "claude-sonnet-4-6",
      devops: "nemotron:70b",
      researcher: "llama3.2:3b",
      analyst: "qwen3:8b",
      verifier: "claude-sonnet-4-6",
    },
  },
  {
    id: "max-quality",
    label: "Max Quality (High VRAM)",
    config: {
      coordinator: "qwen3:14b",
      architect: "qwen2.5-coder:14b",
      coder: "deepseek-coder-v2:236b",
      devops: "nemotron:70b",
      researcher: "qwen3:14b",
      analyst: "llama3.3:70b",
      verifier: "deepseek-r1:70b",
    },
  },
  {
    id: "speed",
    label: "Speed Optimized (Low TTFT)",
    config: {
      coordinator: "qwen3:8b",
      architect: "qwen2.5-coder:7b",
      coder: "qwen2.5-coder:7b",
      devops: "qwen3:8b",
      researcher: "qwen3:1b",
      analyst: "qwen3:8b",
      verifier: "qwen3:8b",
    },
  },
];

export function TeamBuilderSettings() {
  const [roleModels, setRoleModels] = useState<RoleModel[]>(ROLES);
  const [availableModels, setAvailableModels] = useState<AvailableModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  async function fetchData() {
    setLoading(true);
    try {
      // Fetch current team configuration
      const configRes = await fetch(`${API_BASE}/v1/team-builder/config`);
      if (configRes.ok) {
        const config = await configRes.json();
        const updatedRoles = ROLES.map((role) => ({
          ...role,
          model: config[role.role] || "",
        }));
        setRoleModels(updatedRoles);
      }

      // Fetch available Ollama models
      const modelsRes = await fetch(`${API_BASE}/v1/models/ollama`);
      if (modelsRes.ok) {
        const data = await modelsRes.json();
        setAvailableModels(data.models || []);
      }
    } catch (err) {
      console.error("[TeamBuilder] fetchData error:", err);
      setMessage({ type: "error", text: "Failed to load team configuration" });
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setMessage(null);

    try {
      const config: Record<string, string> = {};
      roleModels.forEach((rm) => {
        if (rm.model) {
          config[rm.role] = rm.model;
        }
      });

      const res = await fetch(`${API_BASE}/v1/team-builder/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      setMessage({ type: "success", text: "Team configuration saved successfully" });
    } catch (err) {
      console.error("[TeamBuilder] handleSave error:", err);
      setMessage({ type: "error", text: "Failed to save configuration" });
    } finally {
      setSaving(false);
    }
  }

  function handleModelChange(roleId: string, modelName: string) {
    setRoleModels((prev) =>
      prev.map((rm) => (rm.role === roleId ? { ...rm, model: modelName } : rm))
    );
  }

  function applyPreset(presetId: string) {
    const preset = PRESET_PROFILES.find((p) => p.id === presetId);
    if (!preset) return;

    setRoleModels((prev) =>
      prev.map((rm) => ({
        ...rm,
        model: preset.config[rm.role as keyof typeof preset.config] || "",
      }))
    );

    setMessage({ type: "success", text: `Applied preset: ${preset.label}` });
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-[var(--chat-muted)] text-sm">
        <RefreshCw size={14} className="animate-spin" />
        Loading team configuration...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Users size={18} className="text-[var(--chat-accent)]" />
          <h3 className="text-sm text-[var(--chat-text)] font-medium">Team Builder</h3>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--chat-accent)] text-white text-xs rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {saving ? (
            <RefreshCw size={12} className="animate-spin" />
          ) : (
            <Save size={12} />
          )}
          {saving ? "Saving..." : "Save Config"}
        </button>
      </div>

      {/* Description */}
      <p className="text-xs text-[var(--chat-muted)] leading-relaxed">
        Configure which model each agent role uses in coordinator mode and dev mode.
        Different models can be optimized for different types of work (code, devops, research, etc.).
      </p>

      {/* Status Message */}
      {message && (
        <div
          className={`flex items-center gap-2 p-3 rounded-lg text-xs ${
            message.type === "success"
              ? "bg-green-500/10 text-green-400 border border-green-500/20"
              : "bg-red-500/10 text-red-400 border border-red-500/20"
          }`}
        >
          <AlertCircle size={14} />
          {message.text}
        </div>
      )}

      {/* Preset Profiles */}
      <div>
        <label className="text-xs text-[var(--chat-muted)] mb-2 block">Quick Presets</label>
        <div className="grid grid-cols-2 gap-2">
          {PRESET_PROFILES.map((preset) => (
            <button
              key={preset.id}
              onClick={() => applyPreset(preset.id)}
              className="px-3 py-2 bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-lg text-xs text-[var(--chat-text)] hover:border-[var(--chat-accent)] transition-colors text-left"
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      {/* Role Model Assignments */}
      <div className="space-y-3">
        <label className="text-xs text-[var(--chat-muted)] block">Role Assignments</label>
        <div className="space-y-2">
          {roleModels.map((roleModel) => (
            <div
              key={roleModel.role}
              className="p-3 bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-lg"
            >
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-[var(--chat-text)] mb-0.5">
                    {roleModel.role_label}
                  </div>
                  <div className="text-xs text-[var(--chat-muted)]">
                    {roleModel.description}
                  </div>
                </div>
              </div>
              <select
                value={roleModel.model}
                onChange={(e) => handleModelChange(roleModel.role, e.target.value)}
                className="w-full bg-[var(--chat-surface)] border border-[var(--chat-border)] rounded-lg px-3 py-1.5 text-xs text-[var(--chat-text)] focus:outline-none focus:border-[var(--chat-accent)]"
              >
                <option value="">-- Use default ({roleModel.role === "coordinator" ? "COORDINATOR_MODEL" : "ARCHITECT_MODEL"}) --</option>
                <optgroup label="Local Models (Ollama)">
                  {availableModels.map((model) => (
                    <option key={model.name} value={model.name}>
                      {model.name}
                    </option>
                  ))}
                </optgroup>
                <optgroup label="External Providers">
                  <option value="claude-sonnet-4-6">claude-sonnet-4-6 (Anthropic)</option>
                  <option value="claude-opus-4">claude-opus-4 (Anthropic)</option>
                  <option value="gemini-2.0-flash">gemini-2.0-flash (Google)</option>
                  <option value="gpt-4o">gpt-4o (OpenAI via GitHub Models)</option>
                </optgroup>
              </select>
            </div>
          ))}
        </div>
      </div>

      {/* Help Text */}
      <div className="p-3 bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-lg text-xs text-[var(--chat-muted)] space-y-2">
        <p className="font-medium text-[var(--chat-text)]">💡 Tips:</p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li><strong>Coder:</strong> Use code-specialized models like qwen2.5-coder or Claude Sonnet</li>
          <li><strong>DevOps:</strong> Large models (70B+) handle complex bash/docker better</li>
          <li><strong>Researcher:</strong> Fast models (3B) are ideal for quick context gathering</li>
          <li><strong>Verifier:</strong> High-quality models catch more edge cases</li>
        </ul>
        <p className="pt-2 border-t border-[var(--chat-border)]">
          Changes take effect after restarting agent_runtime container (Python-only, no rebuild needed).
        </p>
      </div>
    </div>
  );
}
