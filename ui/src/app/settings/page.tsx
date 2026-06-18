"use client";

import { ModelSelector } from "@/components/chat/model-selector";
import { ThemeSelector } from "@/components/chat/theme-selector";
import { GitHubConnect } from "@/components/settings/github-connect";
import { ProviderKeysConnect } from "@/components/settings/provider-keys-connect";
import { useToolsStore } from "@/lib/stores/tools-store";
import { useMonitorStore } from "@/lib/stores/monitor-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { DASHBOARDS } from "@/components/monitor/dashboard-selector";
import { useAccess } from "@/lib/hooks/use-access";
import { Settings } from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui";

const TOOL_OPTIONS = [
  { id: "openhands", label: "OpenHands" },
  { id: "ide-devops", label: "IDE (DevOps)" },
  { id: "ide-coding", label: "IDE (Coding)" },
  { id: "open-webui", label: "Open WebUI" },
];

export default function SettingsPage() {
  const { activeTab, setActiveTab } = useToolsStore();
  const { activeDashboard, setActiveDashboard } = useMonitorStore();
  const { isAdmin, loading: accessLoading, securityLevel } = useAccess();
  const navLayout = useSettingsStore((s) => s.navLayout);
  const setNavLayout = useSettingsStore((s) => s.setNavLayout);
  const themePickerMode = useSettingsStore((s) => s.themePickerMode);
  const setThemePickerMode = useSettingsStore((s) => s.setThemePickerMode);
  const soundEnabled = useSettingsStore((s) => s.soundEnabled);
  const setSoundEnabled = useSettingsStore((s) => s.setSoundEnabled);

  const modelAccessMessage = accessLoading
    ? "Checking access level…"
    : isAdmin
      ? "Admin access verified. Claude models are available for this session."
      : `Access level: ${securityLevel || "anonymous"}. Claude models are hidden and non-admin sessions use local-model fallback.`;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 border-b border-[var(--chat-border)] bg-[var(--chat-surface)] px-4 py-3">
        <Settings size={18} className="text-[var(--chat-muted)]" />
        <h1 className="text-sm font-medium text-[var(--chat-text)]">Settings</h1>
      </div>
      <div className="flex-1 overflow-y-auto p-4 md:p-8">
        <div className="max-w-2xl mx-auto space-y-8">
          <SettingsCard title="Appearance">
            <Field label="Theme">
              <ThemeSelector />
              <p className="text-xs text-[var(--chat-muted)] mt-2">
                Memex theme with light, dark, or system-preference modes.
              </p>
            </Field>
            <div className="border-t border-[var(--chat-border)] pt-6 mt-6">
              <Field label="Theme picker style">
                <Select
                  value={themePickerMode}
                  onChange={(v) => setThemePickerMode(v as "popover" | "gallery")}
                  options={[
                    { value: "popover", label: "Popover — compact dropdown in the toolbar" },
                    { value: "gallery", label: "Gallery — full visual gallery modal" },
                  ]}
                />
                <p className="text-xs text-[var(--chat-muted)] mt-2">
                  Controls how the theme picker opens when clicked in the chat toolbar.
                </p>
              </Field>
            </div>
            <div className="border-t border-[var(--chat-border)] pt-6 mt-6">
              <Field label="Navigation layout">
                <Select
                  value={navLayout}
                  onChange={(v) => setNavLayout(v as "sidebar" | "topbar")}
                  options={[
                    { value: "sidebar", label: "Sidebar — collapsible left panel" },
                    { value: "topbar", label: "Top bar — horizontal navigation" },
                  ]}
                />
                <p className="text-xs text-[var(--chat-muted)] mt-2">
                  Switch between a left sidebar and a top navigation bar. Takes effect immediately.
                </p>
              </Field>
            </div>
            <div className="border-t border-[var(--chat-border)] pt-6 mt-6">
              <Field label="UI Sound Effects">
                <Select
                  value={soundEnabled ? "on" : "off"}
                  onChange={(v) => setSoundEnabled(v === "on")}
                  options={[
                    { value: "on", label: "Enabled — Sci-Fi terminal SFX" },
                    { value: "off", label: "Disabled — Silent interface" },
                  ]}
                />
                <p className="text-xs text-[var(--chat-muted)] mt-2">
                  Toggle the dynamic Web Audio API sound effects for button clicks, hovering, and typing.
                </p>
              </Field>
            </div>
          </SettingsCard>

          <SettingsCard title="Chat">
            <Field label="Default model">
              <ModelSelector />
              <p className="text-xs text-[var(--chat-muted)] mt-2">{modelAccessMessage}</p>
            </Field>
          </SettingsCard>

          <SettingsCard title="Connected accounts">
            <Field label="GitHub Models">
              <GitHubConnect />
              <p className="text-xs text-[var(--chat-muted)] mt-2">
                Access GPT-4o, Claude, Llama and others through your GitHub account.
              </p>
            </Field>
            <div className="border-t border-[var(--chat-border)] pt-6 mt-6">
              <Field label="Provider API keys">
                <ProviderKeysConnect />
                <p className="text-xs text-[var(--chat-muted)] mt-2">
                  Bring your own keys for Anthropic, Google Gemini, NVIDIA NIM, and Z.ai GLM.
                </p>
              </Field>
            </div>
          </SettingsCard>

          <SettingsCard title="Workspace defaults">
            <Field label="Default tool tab">
              <Select
                value={activeTab}
                onChange={(v) => setActiveTab(v)}
                options={TOOL_OPTIONS.map((t) => ({ value: t.id, label: t.label }))}
              />
            </Field>
            <div className="mt-5">
              <Field label="Default dashboard">
                <Select
                  value={activeDashboard}
                  onChange={(v) => setActiveDashboard(v)}
                  options={DASHBOARDS.map((d) => ({ value: d.uid, label: d.label }))}
                />
              </Field>
            </div>
          </SettingsCard>

          <SettingsCard title="About">
            <div className="space-y-1 text-sm text-[var(--chat-muted)]">
              <p>Memex Workspace v1.0</p>
              <p>Backend: {process.env.NEXT_PUBLIC_API_BASE_URL || "Agent Runtime"}</p>
            </div>
          </SettingsCard>
        </div>
      </div>
    </div>
  );
}

function SettingsCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card padding="lg">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      {children}
    </Card>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-[var(--chat-text)] mb-2">{label}</label>
      {children}
    </div>
  );
}

function Select({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full bg-[var(--chat-panel)] border border-[var(--chat-border)] rounded-md px-3 py-2 text-sm text-[var(--chat-text)] focus:outline-none focus:border-[var(--chat-accent)] transition-colors"
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}
