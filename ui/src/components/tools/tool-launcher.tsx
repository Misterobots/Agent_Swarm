"use client";

import { useToolsStore } from "@/lib/stores/tools-store";
import { ToolTab } from "./tool-tab";
import { ToolIframe } from "./tool-iframe";
import { ExternalLink } from "lucide-react";
import { Bot, Code2, Laptop, MessageSquare } from "lucide-react";
import type { ToolDefinition } from "@/types/tools";

// Direct port access bypasses Traefik/Authentik middleware which sets X-Frame-Options: DENY
const GATEWAY = process.env.NEXT_PUBLIC_GATEWAY_URL || "http://gateway-node";

const TOOLS: ToolDefinition[] = [
  {
    id: "openhands",
    label: "OpenHands",
    icon: Bot,
    path: `${GATEWAY}:3002`,
    description: "AI Development Agent",
  },
  {
    id: "ide-devops",
    label: "IDE (DevOps)",
    icon: Code2,
    path: `${GATEWAY}:8445`,
    description: "VS Code — Full Access",
  },
  {
    id: "ide-coding",
    label: "IDE (Coding)",
    icon: Laptop,
    path: `${GATEWAY}:8444`,
    description: "VS Code — Sandbox",
  },
  {
    id: "open-webui",
    label: "Open WebUI",
    icon: MessageSquare,
    path: `${GATEWAY}:3000`,
    description: "Chat with local models",
  },
];

export function ToolLauncher() {
  const { activeTab, setActiveTab } = useToolsStore();
  const activeTool = TOOLS.find((t) => t.id === activeTab) || TOOLS[0];
  const iframeUrl = activeTool.path;

  return (
    <div className="flex flex-col h-full">
      {/* Tab Bar */}
      <div className="flex items-center border-b border-zinc-800 bg-[#0a0a14] px-4">
        <div className="flex flex-1 overflow-x-auto">
          {TOOLS.map((tool) => (
            <ToolTab
              key={tool.id}
              tool={tool}
              active={tool.id === activeTab}
              onClick={() => setActiveTab(tool.id)}
            />
          ))}
        </div>
        <a
          href={iframeUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 px-3 py-2 text-xs text-zinc-500 hover:text-cyan-400 transition-colors"
        >
          Open in new tab
          <ExternalLink size={12} />
        </a>
      </div>

      {/* iframe */}
      <ToolIframe url={iframeUrl} label={activeTool.label} />
    </div>
  );
}
