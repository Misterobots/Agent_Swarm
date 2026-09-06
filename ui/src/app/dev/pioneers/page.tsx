"use client";

import { useEffect, useState } from "react";
import { TeamBuilderSettings } from "@/components/settings/team-builder";
import { Card } from "@/components/ui/card";
import { ArrowLeft, Bot, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useIsMobile } from "@/lib/hooks/use-mobile";

interface RoleDefinition {
  id: string;
  label: string;
  description: string;
  defaultModel: string;
}

const ROLES: RoleDefinition[] = [
  { id: "coordinator", label: "Coordinator", description: "Plans work, assigns roles, and keeps a run moving.", defaultModel: "gemma4:31b" },
  { id: "architect", label: "Architect", description: "Shapes technical approaches and system boundaries.", defaultModel: "qwen3-coder:30b" },
  { id: "coder", label: "Coder", description: "Implements changes, edits files, and resolves defects.", defaultModel: "qwen3-coder:30b" },
  { id: "devops", label: "DevOps", description: "Handles infrastructure, containers, and deployment work.", defaultModel: "qwen3-coder:30b" },
  { id: "researcher", label: "Researcher", description: "Investigates code, documentation, and relevant context.", defaultModel: "gemma4:26b" },
  { id: "analyst", label: "Analyst", description: "Interprets findings and highlights useful patterns.", defaultModel: "gemma4:26b" },
  { id: "verifier", label: "Verifier", description: "Reviews results and checks that work meets expectations.", defaultModel: "qwen3:14b" },
];

export default function PioneersPage() {
  const router = useRouter();
  const { isMobile } = useIsMobile();
  const [models, setModels] = useState<Record<string, string>>({});

  useEffect(() => {
    if (isMobile) router.replace("/dev");
  }, [isMobile, router]);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/backend/v1/team-builder/config")
      .then((response) => response.ok ? response.json() : {})
      .then((config: Record<string, string>) => { if (!cancelled) setModels(config); })
      .catch(() => { if (!cancelled) setModels({}); });
    return () => { cancelled = true; };
  }, []);

  if (isMobile) return null;

  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)]">
      <header className="px-6 py-5 border-b border-[var(--chat-border)]">
        <button onClick={() => router.push("/dev")} className="flex items-center gap-2 text-sm text-[var(--chat-muted)] hover:text-[var(--chat-accent)] transition-colors mb-4">
          <ArrowLeft size={16} /> Back to Dev Mode
        </button>
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-lg bg-[color:color-mix(in_srgb,var(--chat-accent)_12%,transparent)] border border-[color:color-mix(in_srgb,var(--chat-accent)_30%,var(--chat-border))]">
            <Users size={26} className="text-[var(--chat-accent)]" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-[var(--chat-text)]">Agent Team</h1>
            <p className="text-sm text-[var(--chat-muted)] mt-1">Review the roles available to a swarm and choose the models that power them.</p>
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto px-6 py-6">
        <div className="max-w-7xl mx-auto space-y-8">
          <section aria-labelledby="team-roles-heading">
            <div className="flex items-center gap-3 mb-4">
              <Bot size={18} className="text-[var(--chat-accent)]" />
              <div>
                <h2 id="team-roles-heading" className="text-lg font-semibold text-[var(--chat-text)]">Configured roles</h2>
                <p className="text-xs text-[var(--chat-muted)]">{ROLES.length} roles; model assignments below reflect your saved configuration when available.</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {ROLES.map((role) => (
                <Card key={role.id} padding="none" className="p-5">
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 shrink-0 rounded-md bg-[var(--chat-panel)] border border-[var(--chat-border)] flex items-center justify-center text-sm font-semibold text-[var(--chat-accent)]">
                      {role.label[0]}
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="text-base font-medium text-[var(--chat-text)]">{role.label}</h3>
                      <p className="text-xs leading-relaxed text-[var(--chat-muted)] mt-1">{role.description}</p>
                      <div className="mt-3 pt-3 border-t border-[var(--chat-border)] text-xs">
                        <span className="text-[var(--chat-muted)]">Model </span>
                        <span className="font-mono text-[var(--chat-text)] break-all">{models[role.id] || role.defaultModel}</span>
                      </div>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </section>

          <section className="bg-[var(--chat-surface)] border border-[var(--chat-border)] rounded-xl p-6" aria-labelledby="team-configuration-heading">
            <h2 id="team-configuration-heading" className="text-lg font-semibold text-[var(--chat-text)]">Team configuration</h2>
            <p className="text-sm text-[var(--chat-muted)] mt-1 mb-6">Change model assignments or apply a preset. Saved assignments apply to your account.</p>
            <TeamBuilderSettings />
          </section>
        </div>
      </main>
    </div>
  );
}
