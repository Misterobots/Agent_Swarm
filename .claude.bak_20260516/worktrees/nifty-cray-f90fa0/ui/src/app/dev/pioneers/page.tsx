"use client";

import { useEffect } from "react";
import { TeamBuilderSettings } from "@/components/settings/team-builder";
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
    <div className="flex flex-col h-full bg-gradient-to-br from-[var(--chat-bg)] via-[var(--chat-surface)] to-[var(--chat-bg)]">
      {/* Header with glowing title */}
      <div className="relative overflow-hidden border-b border-[var(--chat-border)]">
        {/* Animated background grid */}
        <div 
          className="absolute inset-0 opacity-10"
          style={{
            backgroundImage: `
              linear-gradient(90deg, var(--chat-accent) 1px, transparent 1px),
              linear-gradient(180deg, var(--chat-accent) 1px, transparent 1px)
            `,
            backgroundSize: "50px 50px",
            animation: "gridScroll 20s linear infinite"
          }}
        />
        
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
              <div className="absolute inset-0 bg-[var(--chat-accent)] blur-2xl opacity-50 rounded-full" />
              <div className="relative p-4 bg-[var(--chat-accent)] bg-opacity-20 rounded-2xl border border-[var(--chat-accent)] border-opacity-50">
                <Users size={32} className="text-[var(--chat-accent)]" />
              </div>
            </div>
            
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-[var(--chat-accent)] to-cyan-400">
                  Pioneer Academy
                </h1>
                <Sparkles size={20} className="text-[var(--chat-accent)] animate-pulse" />
              </div>
              <p className="text-[var(--chat-muted)] mt-1 text-sm">
                Assemble your elite team of AI pioneers • Configure roles, capabilities, and consciousness parameters
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Mission Brief Section */}
      <div className="px-6 py-4 border-b border-[var(--chat-border)] bg-[var(--chat-surface)] bg-opacity-50">
        <div className="flex items-start gap-4">
          <div className="flex-shrink-0 p-3 bg-cyan-500 bg-opacity-10 rounded-lg border border-cyan-500 border-opacity-30">
            <Cpu size={20} className="text-cyan-400" />
          </div>
          <div className="flex-1">
            <h2 className="text-sm font-semibold text-[var(--chat-text)] mb-1">Mission Brief</h2>
            <p className="text-xs text-[var(--chat-muted)] leading-relaxed">
              Each Pioneer is a specialized AI agent with unique capabilities. Configure their neural architecture, 
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
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            <span className="text-[var(--chat-muted)]">Neural Network:</span>
            <span className="text-[var(--chat-text)] font-mono">ONLINE</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-cyan-500" />
            <span className="text-[var(--chat-muted)]">Swarm Status:</span>
            <span className="text-[var(--chat-text)] font-mono">READY</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-purple-500" />
            <span className="text-[var(--chat-muted)]">Consciousness:</span>
            <span className="text-[var(--chat-text)] font-mono">SYNCHRONIZED</span>
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
              <div className="group relative bg-[var(--chat-surface)] border border-[var(--chat-border)] rounded-xl p-5 transition-all hover:border-[var(--chat-accent)] hover:shadow-lg">
                <div className="absolute top-3 right-3">
                  <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                </div>
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 w-12 h-12 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white font-bold text-lg">
                    A
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-semibold text-[var(--chat-text)] mb-1">Ada</h3>
                    <div className="inline-block px-2 py-0.5 bg-purple-500 bg-opacity-20 border border-purple-500 border-opacity-30 rounded text-xs text-purple-400 mb-2">
                      COORDINATOR
                    </div>
                    <p className="text-xs text-[var(--chat-muted)] leading-relaxed mb-3">
                      Mission planner and orchestrator. Decomposes complex tasks, assigns work to specialists, and ensures coordination across the swarm.
                    </p>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-[var(--chat-muted)]">Neural Core:</span>
                      <span className="text-[var(--chat-text)] font-mono">qwen3:14b</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Turing - Architect */}
              <div className="group relative bg-[var(--chat-surface)] border border-[var(--chat-border)] rounded-xl p-5 transition-all hover:border-[var(--chat-accent)] hover:shadow-lg">
                <div className="absolute top-3 right-3">
                  <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                </div>
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center text-white font-bold text-lg">
                    T
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-semibold text-[var(--chat-text)] mb-1">Turing</h3>
                    <div className="inline-block px-2 py-0.5 bg-blue-500 bg-opacity-20 border border-blue-500 border-opacity-30 rounded text-xs text-blue-400 mb-2">
                      ARCHITECT
                    </div>
                    <p className="text-xs text-[var(--chat-muted)] leading-relaxed mb-3">
                      System designer and technical lead. Plans architectures, designs data flows, and defines technical specifications for the team.
                    </p>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-[var(--chat-muted)]">Neural Core:</span>
                      <span className="text-[var(--chat-text)] font-mono">qwen2.5-coder:14b</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Grace - Coder */}
              <div className="group relative bg-[var(--chat-surface)] border border-[var(--chat-border)] rounded-xl p-5 transition-all hover:border-[var(--chat-accent)] hover:shadow-lg">
                <div className="absolute top-3 right-3">
                  <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                </div>
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 w-12 h-12 rounded-full bg-gradient-to-br from-green-500 to-emerald-500 flex items-center justify-center text-white font-bold text-lg">
                    G
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-semibold text-[var(--chat-text)] mb-1">Grace</h3>
                    <div className="inline-block px-2 py-0.5 bg-green-500 bg-opacity-20 border border-green-500 border-opacity-30 rounded text-xs text-green-400 mb-2">
                      CODER
                    </div>
                    <p className="text-xs text-[var(--chat-muted)] leading-relaxed mb-3">
                      Primary implementation specialist. Writes production code, implements features, handles file operations, and debugs complex issues.
                    </p>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-[var(--chat-muted)]">Neural Core:</span>
                      <span className="text-[var(--chat-text)] font-mono">qwen2.5-coder:14b</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Dennis - DevOps */}
              <div className="group relative bg-[var(--chat-surface)] border border-[var(--chat-border)] rounded-xl p-5 transition-all hover:border-[var(--chat-accent)] hover:shadow-lg">
                <div className="absolute top-3 right-3">
                  <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                </div>
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 w-12 h-12 rounded-full bg-gradient-to-br from-orange-500 to-red-500 flex items-center justify-center text-white font-bold text-lg">
                    D
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-semibold text-[var(--chat-text)] mb-1">Dennis</h3>
                    <div className="inline-block px-2 py-0.5 bg-orange-500 bg-opacity-20 border border-orange-500 border-opacity-30 rounded text-xs text-orange-400 mb-2">
                      DEVOPS
                    </div>
                    <p className="text-xs text-[var(--chat-muted)] leading-relaxed mb-3">
                      Infrastructure guardian. Manages containers, orchestrates deployments, writes bash scripts, and maintains system reliability.
                    </p>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-[var(--chat-muted)]">Neural Core:</span>
                      <span className="text-[var(--chat-text)] font-mono">qwen3:8b</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Margaret - Researcher */}
              <div className="group relative bg-[var(--chat-surface)] border border-[var(--chat-border)] rounded-xl p-5 transition-all hover:border-[var(--chat-accent)] hover:shadow-lg">
                <div className="absolute top-3 right-3">
                  <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                </div>
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 w-12 h-12 rounded-full bg-gradient-to-br from-yellow-500 to-amber-500 flex items-center justify-center text-white font-bold text-lg">
                    M
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-semibold text-[var(--chat-text)] mb-1">Margaret</h3>
                    <div className="inline-block px-2 py-0.5 bg-yellow-500 bg-opacity-20 border border-yellow-500 border-opacity-30 rounded text-xs text-yellow-400 mb-2">
                      RESEARCHER
                    </div>
                    <p className="text-xs text-[var(--chat-muted)] leading-relaxed mb-3">
                      Knowledge seeker and context gatherer. Explores codebases, investigates patterns, searches documentation, and builds understanding.
                    </p>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-[var(--chat-muted)]">Neural Core:</span>
                      <span className="text-[var(--chat-text)] font-mono">llama3.2:3b</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Claude - Analyst */}
              <div className="group relative bg-[var(--chat-surface)] border border-[var(--chat-border)] rounded-xl p-5 transition-all hover:border-[var(--chat-accent)] hover:shadow-lg">
                <div className="absolute top-3 right-3">
                  <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                </div>
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 w-12 h-12 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center text-white font-bold text-lg">
                    C
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-semibold text-[var(--chat-text)] mb-1">Claude</h3>
                    <div className="inline-block px-2 py-0.5 bg-indigo-500 bg-opacity-20 border border-indigo-500 border-opacity-30 rounded text-xs text-indigo-400 mb-2">
                      ANALYST
                    </div>
                    <p className="text-xs text-[var(--chat-muted)] leading-relaxed mb-3">
                      Data interpreter and insights provider. Analyzes patterns, extracts meaning from data, and provides strategic recommendations.
                    </p>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-[var(--chat-muted)]">Neural Core:</span>
                      <span className="text-[var(--chat-text)] font-mono">qwen3:8b</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Dijkstra - Verifier */}
              <div className="group relative bg-[var(--chat-surface)] border border-[var(--chat-border)] rounded-xl p-5 transition-all hover:border-[var(--chat-accent)] hover:shadow-lg">
                <div className="absolute top-3 right-3">
                  <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                </div>
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 w-12 h-12 rounded-full bg-gradient-to-br from-red-500 to-pink-500 flex items-center justify-center text-white font-bold text-lg">
                    D
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-semibold text-[var(--chat-text)] mb-1">Dijkstra</h3>
                    <div className="inline-block px-2 py-0.5 bg-red-500 bg-opacity-20 border border-red-500 border-opacity-30 rounded text-xs text-red-400 mb-2">
                      VERIFIER
                    </div>
                    <p className="text-xs text-[var(--chat-muted)] leading-relaxed mb-3">
                      Quality guardian and code reviewer. Validates implementations, checks for errors, ensures standards, and maintains excellence.
                    </p>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-[var(--chat-muted)]">Neural Core:</span>
                      <span className="text-[var(--chat-text)] font-mono">qwen3:8b</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Team Configuration Section */}
          <div className="bg-[var(--chat-surface)] border border-[var(--chat-border)] rounded-xl p-6 shadow-2xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-1 h-6 bg-cyan-500" />
              <h2 className="text-xl font-bold text-[var(--chat-text)]">Team Configuration</h2>
            </div>
            <p className="text-sm text-[var(--chat-muted)] mb-6">
              Customize which AI models power each Pioneer. Choose from local Ollama models or cloud providers.
            </p>
            <TeamBuilderSettings />
          </div>
        </div>
      </div>

      {/* CSS for grid animation */}
      <style jsx>{`
        @keyframes gridScroll {
          0% {
            transform: translateY(0) translateX(0);
          }
          100% {
            transform: translateY(50px) translateX(50px);
          }
        }
      `}</style>
    </div>
  );
}
