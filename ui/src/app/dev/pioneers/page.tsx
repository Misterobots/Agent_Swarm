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

      {/* Main Content - Team Builder */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="max-w-7xl mx-auto">
          {/* Info Cards */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="p-4 bg-[var(--chat-surface)] border border-[var(--chat-border)] rounded-lg hover:border-[var(--chat-accent)] transition-colors">
              <div className="text-2xl font-bold text-[var(--chat-accent)] mb-1">∞</div>
              <div className="text-xs text-[var(--chat-muted)]">Model Variants</div>
              <div className="text-sm text-[var(--chat-text)] mt-2">Deploy specialized models for each role</div>
            </div>
            <div className="p-4 bg-[var(--chat-surface)] border border-[var(--chat-border)] rounded-lg hover:border-cyan-500 transition-colors">
              <div className="text-2xl font-bold text-cyan-400 mb-1">↕</div>
              <div className="text-xs text-[var(--chat-muted)]">Dynamic Scaling</div>
              <div className="text-sm text-[var(--chat-text)] mt-2">Swarm adapts to task complexity</div>
            </div>
            <div className="p-4 bg-[var(--chat-surface)] border border-[var(--chat-border)] rounded-lg hover:border-purple-500 transition-colors">
              <div className="text-2xl font-bold text-purple-400 mb-1">⚡</div>
              <div className="text-xs text-[var(--chat-muted)]">Live Collaboration</div>
              <div className="text-sm text-[var(--chat-text)] mt-2">Real-time inter-agent communication</div>
            </div>
          </div>

          {/* Team Builder Component */}
          <div className="bg-[var(--chat-surface)] border border-[var(--chat-border)] rounded-xl p-6 shadow-2xl">
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
