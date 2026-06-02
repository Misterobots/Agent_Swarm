"use client";

import { useEffect } from "react";
import { TeamBuilderSettings } from "@/components/settings/team-builder";
import { Card } from "@/components/ui/card";
import { ArrowLeft, Sparkles, Users, Cpu } from "lucide-react";
import { useRouter } from "next/navigation";
import { useIsMobile } from "@/lib/hooks/use-mobile";

export default function PioneersPage() {
  const router = useRouter();
  const { isMobile } = useIsMobile();

  // Redirect to dev on mobile
  useEffect(() => {
    if (isMobile) router.replace("/dev");
  }, [isMobile, router]);

  if (isMobile) return null;

  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)]">
      {/* Header */}
      <div className="relative overflow-hidden border-b border-[var(--chat-border)]">
        <div className="relative px-6 py-6">
          <button
            onClick={() => router.push("/dev")}
            className="flex items-center gap-2 text-sm text-[var(--chat-muted)] hover:text-[var(--chat-accent)] transition-colors mb-4 group"
          >
            <ArrowLeft size={16} className="group-hover:-translate-x-1 transition-transform" />
            Back to Dev Mode
          </button>

          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="relative p-4 bg-[color:color-mix(in_srgb,var(--chat-accent)_12%,transparent)] rounded-2xl border border-[color:color-mix(in_srgb,var(--chat-accent)_30%,var(--chat-border))]">
                <Users size={32} className="text-[var(--chat-accent)]" />
              </div>
            </div>

            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-3xl font-bold text-[var(--chat-text)]">
                  Pioneer Academy
                </h1>
                <Sparkles size={20} className="text-[var(--chat-accent)]" />
              </div>
              <p className="text-[var(--chat-muted)] mt-1 text-sm">
                Assemble your elite team of AI pioneers • Configure roles, capabilities, and Model settings
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Mission Brief Section */}
      <div className="px-6 py-4 border-b border-[var(--chat-border)] bg-[var(--chat-surface)] bg-opacity-50">
        <div className="flex items-start gap-4">
          <div className="flex-shrink-0 p-3 bg-[color:color-mix(in_srgb,var(--chat-accent)_10%,transparent)] rounded-lg border border-[color:color-mix(in_srgb,var(--chat-accent)_25%,var(--chat-border))]">
            <Cpu size={20} className="text-[var(--chat-accent)]" />
          </div>
          <div className="flex-1">
            <h2 className="text-sm font-semibold text-[var(--chat-text)] mb-1">Mission Brief</h2>
            <p className="text-xs text-[var(--chat-muted)] leading-relaxed">
              Each Pioneer is a specialized AI agent with unique capabilities. Configure their architecture,
              assign tools and knowledge bases, and define their operational parameters. Your team will autonomously
              collaborate on complex tasks, with each agent contributing their expertise to the swarm's collective intelligence.
            </p>
          </div>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="px-6 py-3 bg-[var(--chat-input-bg)] border-b border-[var(--chat-border)]">
        <div className="flex items-center gap-6 text-xs">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[var(--chat-muted)]">Neural Network:</span>
            <span className="text-[var(--chat-text)] font-mono">ONLINE</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="text-[var(--chat-muted)]">Swarm Status:</span>
            <span className="text-[var(--chat-text)] font-mono">READY</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-[var(--chat-accent)]" />
            <span className="text-[var(--chat-muted)]">Agents:</span>
            <span className="text-[var(--chat-text)] font-mono">Active</span>
          </div>
        </div>
      </div>

      {/* Main Content - Pioneer Roster */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="max-w-7xl mx-auto">
          {/* Pioneer Roster Grid */}
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-1 h-8 bg-[var(--chat-accent)]" />
              <h2 className="text-2xl font-bold text-[var(--chat-text)]">Active Pioneers</h2>
              <span className="text-sm text-[var(--chat-muted)]">• 7 agents deployed</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {/* Ada - Coordinator */}
              <Card interactive padding="none" className="group relative p-5">
                <div className="absolute top-3 right-3">
                  <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                </div>
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 bg-[var(--chat-panel)] border border-[var(--chat-border)] w-10 h-10 rounded-md flex items-center justify-center text-[var(--chat-text)] font-semibold">
                    A
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-semibold text-[var(--chat-text)] mb-1">Ada</h3>
                    <div className="inline-block bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent-strong)] border border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))] rounded-full px-2 py-0.5 text-[11px] font-medium mb-2">
                      COORDINATOR
                    </div>
                    <p className="text-xs text-[var(--chat-muted)] leading-relaxed mb-3">
                      Mission planner and orchestrator. Decomposes complex tasks, assigns work to specialists, and ensures coordination across the swarm.
                    </p>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-[var(--chat-muted)]">Model:</span>
                      <span className="text-[var(--chat-text)] font-mono">qwen3:14b</span>
                    </div>
                  </div>
                </div>
              </Card>

              {/* Turing - Architect */}
              <Card interactive padding="none" className="group relative p-5">
                <div className="absolute top-3 right-3">
                  <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                </div>
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 bg-[var(--chat-panel)] border border-[var(--chat-border)] w-10 h-10 rounded-md flex items-center justify-center text-[var(--chat-text)] font-semibold">
                    T
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-semibold text-[var(--chat-text)] mb-1">Turing</h3>
                    <div className="inline-block bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent-strong)] border border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))] rounded-full px-2 py-0.5 text-[11px] font-medium mb-2">
                      ARCHITECT
                    </div>
                    <p className="text-xs text-[var(--chat-muted)] leading-relaxed mb-3">
                      System designer and technical lead. Plans architectures, designs data flows, and defines technical specifications for the team.
                    </p>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-[var(--chat-muted)]">Model:</span>
                      <span className="text-[var(--chat-text)] font-mono">qwen2.5-coder:14b</span>
                    </div>
                  </div>
                </div>
              </Card>

              {/* Grace - Coder */}
              <Card interactive padding="none" className="group relative p-5">
                <div className="absolute top-3 right-3">
                  <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                </div>
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 bg-[var(--chat-panel)] border border-[var(--chat-border)] w-10 h-10 rounded-md flex items-center justify-center text-[var(--chat-text)] font-semibold">
                    G
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-semibold text-[var(--chat-text)] mb-1">Grace</h3>
                    <div className="inline-block bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent-strong)] border border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))] rounded-full px-2 py-0.5 text-[11px] font-medium mb-2">
                      CODER
                    </div>
                    <p className="text-xs text-[var(--chat-muted)] leading-relaxed mb-3">
                      Primary implementation specialist. Writes production code, implements features, handles file operations, and debugs complex issues.
                    </p>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-[var(--chat-muted)]">Model:</span>
                      <span className="text-[var(--chat-text)] font-mono">qwen2.5-coder:14b</span>
                    </div>
                  </div>
                </div>
              </Card>

              {/* Dennis - DevOps */}
              <Card interactive padding="none" className="group relative p-5">
                <div className="absolute top-3 right-3">
                  <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                </div>
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 bg-[var(--chat-panel)] border border-[var(--chat-border)] w-10 h-10 rounded-md flex items-center justify-center text-[var(--chat-text)] font-semibold">
                    D
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-semibold text-[var(--chat-text)] mb-1">Dennis</h3>
                    <div className="inline-block bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent-strong)] border border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))] rounded-full px-2 py-0.5 text-[11px] font-medium mb-2">
                      DEVOPS
                    </div>
                    <p className="text-xs text-[var(--chat-muted)] leading-relaxed mb-3">
                      Infrastructure guardian. Manages containers, orchestrates deployments, writes bash scripts, and maintains system reliability.
                    </p>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-[var(--chat-muted)]">Model:</span>
                      <span className="text-[var(--chat-text)] font-mono">qwen3:8b</span>
                    </div>
                  </div>
                </div>
              </Card>

              {/* Margaret - Researcher */}
              <Card interactive padding="none" className="group relative p-5">
                <div className="absolute top-3 right-3">
                  <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                </div>
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 bg-[var(--chat-panel)] border border-[var(--chat-border)] w-10 h-10 rounded-md flex items-center justify-center text-[var(--chat-text)] font-semibold">
                    M
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-semibold text-[var(--chat-text)] mb-1">Margaret</h3>
                    <div className="inline-block bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent-strong)] border border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))] rounded-full px-2 py-0.5 text-[11px] font-medium mb-2">
                      RESEARCHER
                    </div>
                    <p className="text-xs text-[var(--chat-muted)] leading-relaxed mb-3">
                      Knowledge seeker and context gatherer. Explores codebases, investigates patterns, searches documentation, and builds understanding.
                    </p>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-[var(--chat-muted)]">Model:</span>
                      <span className="text-[var(--chat-text)] font-mono">llama3.2:3b</span>
                    </div>
                  </div>
                </div>
              </Card>

              {/* Claude - Analyst */}
              <Card interactive padding="none" className="group relative p-5">
                <div className="absolute top-3 right-3">
                  <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                </div>
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 bg-[var(--chat-panel)] border border-[var(--chat-border)] w-10 h-10 rounded-md flex items-center justify-center text-[var(--chat-text)] font-semibold">
                    C
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-semibold text-[var(--chat-text)] mb-1">Claude</h3>
                    <div className="inline-block bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent-strong)] border border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))] rounded-full px-2 py-0.5 text-[11px] font-medium mb-2">
                      ANALYST
                    </div>
                    <p className="text-xs text-[var(--chat-muted)] leading-relaxed mb-3">
                      Data interpreter and insights provider. Analyzes patterns, extracts meaning from data, and provides strategic recommendations.
                    </p>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-[var(--chat-muted)]">Model:</span>
                      <span className="text-[var(--chat-text)] font-mono">qwen3:8b</span>
                    </div>
                  </div>
                </div>
              </Card>

              {/* Dijkstra - Verifier */}
              <Card interactive padding="none" className="group relative p-5">
                <div className="absolute top-3 right-3">
                  <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                </div>
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 bg-[var(--chat-panel)] border border-[var(--chat-border)] w-10 h-10 rounded-md flex items-center justify-center text-[var(--chat-text)] font-semibold">
                    D
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-semibold text-[var(--chat-text)] mb-1">Dijkstra</h3>
                    <div className="inline-block bg-[color:color-mix(in_srgb,var(--chat-accent)_18%,transparent)] text-[var(--chat-accent-strong)] border border-[color:color-mix(in_srgb,var(--chat-accent)_40%,var(--chat-border))] rounded-full px-2 py-0.5 text-[11px] font-medium mb-2">
                      VERIFIER
                    </div>
                    <p className="text-xs text-[var(--chat-muted)] leading-relaxed mb-3">
                      Quality guardian and code reviewer. Validates implementations, checks for errors, ensures standards, and maintains excellence.
                    </p>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-[var(--chat-muted)]">Model:</span>
                      <span className="text-[var(--chat-text)] font-mono">qwen3:8b</span>
                    </div>
                  </div>
                </div>
              </Card>
            </div>
          </div>

          {/* Team Configuration Section */}
          <div className="bg-[var(--chat-surface)] border border-[var(--chat-border)] rounded-xl p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-1 h-6 bg-[var(--chat-accent)]" />
              <h2 className="text-xl font-bold text-[var(--chat-text)]">Team Configuration</h2>
            </div>
            <p className="text-sm text-[var(--chat-muted)] mb-6">
              Customize which AI models power each Pioneer. Choose from local Ollama models or cloud providers.
            </p>
            <TeamBuilderSettings />
          </div>
        </div>
      </div>
    </div>
  );
}
