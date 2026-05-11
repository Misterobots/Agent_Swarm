"use client";

import { useState } from "react";
import {
  Zap,
  RotateCw,
  Upload,
  Download,
  Terminal,
  Package,
  Layers,
  Server,
  Play,
  ChevronDown,
  Loader2,
} from "lucide-react";
import { useDevStore } from "@/lib/stores/dev-store";
import { cn } from "@/lib/utils/cn";

interface QuickAction {
  id: string;
  label: string;
  icon: React.ReactNode;
  description: string;
  category: "git" | "docker" | "deploy" | "terminal";
  action: () => Promise<void>;
}

export function QuickActionsToolbar() {
  const { selectedNode } = useDevStore();
  const [loading, setLoading] = useState<string | null>(null);
  const [showMenu, setShowMenu] = useState(false);

  const executeAction = async (actionId: string, action: () => Promise<void>) => {
    setLoading(actionId);
    try {
      await action();
    } catch (error) {
      console.error(`Action ${actionId} failed:`, error);
    } finally {
      setLoading(null);
    }
  };

  const actions: QuickAction[] = [
    {
      id: "git-pull-all",
      label: "Pull All Nodes",
      icon: <Download size={14} />,
      description: "Git pull on Lovelace, Turing, and Hopper",
      category: "git",
      action: async () => {
        await Promise.all([
          fetch("/api/devops/git/pull", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ node: "lovelace" }),
          }),
          fetch("/api/devops/git/pull", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ node: "turing" }),
          }),
          fetch("/api/devops/git/pull", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ node: "hopper" }),
          }),
        ]);
      },
    },
    {
      id: "git-push",
      label: "Push Current",
      icon: <Upload size={14} />,
      description: "Git push current node",
      category: "git",
      action: async () => {
        await fetch("/api/devops/git/push", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ node: selectedNode }),
        });
      },
    },
    {
      id: "restart-runtime",
      label: "Restart Runtime",
      icon: <RotateCw size={14} />,
      description: "Restart agent_runtime container",
      category: "docker",
      action: async () => {
        await fetch("/api/devops/ssh", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            node: "turing",
            command: "docker restart agent_runtime",
          }),
        });
      },
    },
    {
      id: "restart-ui",
      label: "Restart UI",
      icon: <Layers size={14} />,
      description: "Restart Memex UI container",
      category: "docker",
      action: async () => {
        await fetch("/api/devops/ssh", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            node: "turing",
            command: "docker restart hive_ui",
          }),
        });
      },
    },
    {
      id: "rebuild-ui",
      label: "Rebuild UI",
      icon: <Package size={14} />,
      description: "Rebuild and restart Memex UI",
      category: "deploy",
      action: async () => {
        await fetch("/api/devops/ssh", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            node: "turing",
            command:
              "cd /home/misterobots/Home_AI_Lab && docker compose -f turing_gateway/docker-compose.yml build hive-ui && docker compose -f turing_gateway/docker-compose.yml up -d hive-ui",
          }),
        });
      },
    },
    {
      id: "restart-all",
      label: "Restart All Services",
      icon: <Server size={14} />,
      description: "Restart all Docker services",
      category: "docker",
      action: async () => {
        await fetch("/api/devops/ssh", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            node: "turing",
            command:
              "docker compose -f /home/misterobots/Home_AI_Lab/turing_gateway/docker-compose.yml restart",
          }),
        });
      },
    },
    {
      id: "ssh-turing",
      label: "SSH Turing",
      icon: <Terminal size={14} />,
      description: "Open SSH connection to Turing",
      category: "terminal",
      action: async () => {
        // TODO: Open terminal with SSH connection
        console.log("Opening SSH to Turing...");
      },
    },
    {
      id: "deploy-full",
      label: "Full Deploy",
      icon: <Play size={14} />,
      description: "Pull + rebuild + restart all services",
      category: "deploy",
      action: async () => {
        await fetch("/api/devops/deploy", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target: "all" }),
        });
      },
    },
  ];

  const categorizedActions = {
    git: actions.filter((a) => a.category === "git"),
    docker: actions.filter((a) => a.category === "docker"),
    deploy: actions.filter((a) => a.category === "deploy"),
    terminal: actions.filter((a) => a.category === "terminal"),
  };

  // Most frequently used actions for compact display
  const primaryActions = [
    actions.find((a) => a.id === "git-pull-all")!,
    actions.find((a) => a.id === "restart-runtime")!,
    actions.find((a) => a.id === "rebuild-ui")!,
  ];

  return (
    <div className="relative flex items-center gap-2 px-4 py-2 bg-[var(--chat-surface)]">
      <div className="flex items-center gap-1.5 mr-2">
        <Zap size={13} className="text-[var(--chat-accent)]" />
        <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--chat-subtle)]">
          Quick Actions
        </span>
      </div>

      {/* Primary Actions */}
      <div className="flex items-center gap-1.5">
        {primaryActions.map((action) => {
          const busy = loading === action.id;
          return (
            <button
              key={action.id}
              onClick={() => executeAction(action.id, action.action)}
              disabled={busy}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-[12px] font-medium rounded-md bg-[var(--chat-panel)] hover:bg-[var(--chat-elevated)] border border-[var(--chat-border)] hover:border-[color:color-mix(in_srgb,var(--chat-border)_50%,var(--chat-text))] text-[var(--chat-text)] transition-colors disabled:opacity-50"
              title={action.description}
            >
              <span className="text-[var(--chat-muted)]">
                {busy ? <Loader2 size={13} className="animate-spin" /> : action.icon}
              </span>
              <span className="hidden md:inline">{action.label}</span>
            </button>
          );
        })}
      </div>

      {/* More Actions Dropdown */}
      <div className="relative ml-auto">
        <button
          onClick={() => setShowMenu(!showMenu)}
          className="inline-flex items-center gap-1 px-2.5 py-1.5 text-[12px] font-medium rounded-md bg-[var(--chat-panel)] hover:bg-[var(--chat-elevated)] border border-[var(--chat-border)] hover:border-[color:color-mix(in_srgb,var(--chat-border)_50%,var(--chat-text))] text-[var(--chat-text)] transition-colors"
        >
          More
          <ChevronDown size={12} className={cn("transition-transform text-[var(--chat-subtle)]", showMenu && "rotate-180")} />
        </button>

        {showMenu && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setShowMenu(false)} />
            <div
              className="absolute right-0 top-full mt-2 w-72 rounded-md overflow-hidden z-50 max-h-96 overflow-y-auto theme-picker-enter"
              style={{
                background: "var(--chat-elevated)",
                border: "1px solid var(--chat-border)",
                boxShadow: "var(--elev-3)",
              }}
            >
              {Object.entries(categorizedActions).map(([category, categoryActions], idx, all) => (
                <div
                  key={category}
                  className={cn(idx !== all.length - 1 && "border-b border-[var(--divider)]")}
                >
                  <div
                    className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--chat-subtle)]"
                    style={{ background: "color-mix(in srgb, var(--chat-panel) 60%, transparent)" }}
                  >
                    {category}
                  </div>
                  <div className="p-1">
                    {categoryActions.map((action) => {
                      const busy = loading === action.id;
                      return (
                        <button
                          key={action.id}
                          onClick={() => {
                            executeAction(action.id, action.action);
                            setShowMenu(false);
                          }}
                          disabled={busy}
                          className="w-full flex items-start gap-2.5 px-2.5 py-2 text-left rounded-sm hover:bg-[var(--hover-tint)] transition-colors disabled:opacity-50"
                        >
                          <span className="mt-0.5 text-[var(--chat-muted)] flex-shrink-0">
                            {busy ? <Loader2 size={13} className="animate-spin" /> : action.icon}
                          </span>
                          <div className="flex-1 min-w-0">
                            <div className="text-[13px] font-medium text-[var(--chat-text)]">
                              {action.label}
                            </div>
                            <div className="text-[11px] text-[var(--chat-muted)] mt-0.5 truncate">
                              {action.description}
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
      <div className="absolute bottom-0 left-0 right-0 divider" />
    </div>
  );
}
