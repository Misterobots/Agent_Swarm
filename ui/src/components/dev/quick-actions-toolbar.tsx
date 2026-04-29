"use client";

import { useState } from "react";
import { 
  Zap, 
  GitPullRequest, 
  RotateCw, 
  Upload, 
  Download, 
  Terminal, 
  Package,
  Layers,
  Server,
  Play,
  ChevronDown
} from "lucide-react";
import { useDevStore } from "@/lib/stores/dev-store";

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
      description: "Restart hive_ui container",
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
      description: "Rebuild and restart hive-ui",
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
    <div className="relative flex items-center gap-2 px-3 py-2 bg-[var(--chat-input-bg)] border-b border-[var(--chat-border)]">
      <div className="flex items-center gap-2 mr-2">
        <Zap size={14} className="text-[var(--chat-accent)]" />
        <span className="text-xs font-medium text-[var(--chat-text)]">Quick Actions</span>
      </div>

      {/* Primary Actions */}
      <div className="flex items-center gap-1">
        {primaryActions.map((action) => (
          <button
            key={action.id}
            onClick={() => executeAction(action.id, action.action)}
            disabled={loading === action.id}
            className="flex items-center gap-1.5 px-2 py-1.5 text-xs bg-[var(--chat-bg)] hover:bg-[var(--chat-hover)] border border-[var(--chat-border)] rounded transition-colors disabled:opacity-50"
            title={action.description}
          >
            {action.icon}
            <span className="hidden md:inline">{action.label}</span>
            {loading === action.id && (
              <span className="inline-block animate-spin">⏳</span>
            )}
          </button>
        ))}
      </div>

      {/* More Actions Dropdown */}
      <div className="relative ml-auto">
        <button
          onClick={() => setShowMenu(!showMenu)}
          className="flex items-center gap-1 px-2 py-1.5 text-xs bg-[var(--chat-bg)] hover:bg-[var(--chat-hover)] border border-[var(--chat-border)] rounded transition-colors"
        >
          More
          <ChevronDown size={12} />
        </button>

        {showMenu && (
          <>
            {/* Backdrop */}
            <div
              className="fixed inset-0 z-40"
              onClick={() => setShowMenu(false)}
            />

            {/* Dropdown Menu */}
            <div className="absolute right-0 top-full mt-1 w-64 bg-[var(--chat-bg)] border border-[var(--chat-border)] rounded-lg shadow-lg z-50 max-h-96 overflow-y-auto">
              {Object.entries(categorizedActions).map(([category, categoryActions]) => (
                <div key={category} className="border-b border-[var(--chat-border)] last:border-b-0">
                  <div className="px-3 py-2 text-xs font-semibold text-[var(--chat-muted)] uppercase bg-[var(--chat-input-bg)]">
                    {category}
                  </div>
                  <div className="p-1">
                    {categoryActions.map((action) => (
                      <button
                        key={action.id}
                        onClick={() => {
                          executeAction(action.id, action.action);
                          setShowMenu(false);
                        }}
                        disabled={loading === action.id}
                        className="w-full flex items-start gap-2 px-2 py-2 text-xs text-left hover:bg-[var(--chat-hover)] rounded transition-colors disabled:opacity-50"
                      >
                        <span className="mt-0.5">{action.icon}</span>
                        <div className="flex-1">
                          <div className="font-medium text-[var(--chat-text)]">{action.label}</div>
                          <div className="text-[var(--chat-muted)] text-xs mt-0.5">
                            {action.description}
                          </div>
                        </div>
                        {loading === action.id && (
                          <span className="inline-block animate-spin">⏳</span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
