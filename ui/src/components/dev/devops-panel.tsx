"use client";

import { useState, useEffect } from "react";
import { 
  Server, 
  Play, 
  Square, 
  RotateCw, 
  Terminal as TerminalIcon, 
  Activity,
  AlertCircle,
  CheckCircle,
  Circle,
  ExternalLink
} from "lucide-react";
import { useDevStore } from "@/lib/stores/dev-store";

interface PioneerNode {
  name: string;
  ip: string;
  status: "online" | "offline" | "unknown";
  isLocal: boolean;
}

interface Service {
  name: string;
  container?: string;
  node: string;
  status: "running" | "stopped" | "error" | "unknown";
  port?: number;
}

const PIONEER_NODES: PioneerNode[] = [
  { name: "Lovelace", ip: "192.168.2.101", status: "unknown", isLocal: true },
  { name: "Turing", ip: "192.168.2.103", status: "unknown", isLocal: false },
  { name: "Hopper", ip: "192.168.2.102", status: "unknown", isLocal: false },
  { name: "BMO", ip: "192.168.2.106", status: "unknown", isLocal: false },
];

const SERVICES: Service[] = [
  { name: "Agent Runtime", container: "agent_runtime", node: "Turing", status: "unknown", port: 5001 },
  { name: "Memex UI", container: "memex_ui", node: "Turing", status: "unknown", port: 3000 },
  { name: "PostgreSQL", container: "postgres", node: "Hopper", status: "unknown", port: 5432 },
  { name: "Redis", container: "redis", node: "Hopper", status: "unknown", port: 6379 },
  { name: "Langfuse", container: "langfuse", node: "Hopper", status: "unknown", port: 3001 },
  { name: "Ollama", container: "ollama", node: "Turing", status: "unknown", port: 11434 },
  { name: "Ollama (Lovelace)", node: "Lovelace", status: "unknown", port: 11434 },
];

export function DevOpsPanel() {
  const { selectedNode } = useDevStore();
  const [nodes, setNodes] = useState<PioneerNode[]>(PIONEER_NODES);
  const [services, setServices] = useState<Service[]>(SERVICES);
  const [loading, setLoading] = useState(false);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "running":
      case "online":
        return <CheckCircle className="text-green-500" size={16} />;
      case "stopped":
      case "offline":
        return <Circle className="text-gray-500" size={16} />;
      case "error":
        return <AlertCircle className="text-red-500" size={16} />;
      default:
        return <Circle className="text-yellow-500" size={16} />;
    }
  };

  const refreshStatus = async () => {
    setLoading(true);
    try {
      // TODO: Call backend API to get real status
      // For now, simulate network check
      const response = await fetch("/api/devops/status");
      if (response.ok) {
        const data = await response.json();
        setNodes(data.nodes || nodes);
        setServices(data.services || services);
      }
    } catch (error) {
      console.error("Failed to refresh status:", error);
    } finally {
      setLoading(false);
    }
  };

  const executeSSH = async (node: string, command: string) => {
    try {
      const response = await fetch("/api/devops/ssh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ node, command }),
      });
      const data = await response.json();
      console.log("SSH result:", data);
      // TODO: Show result in terminal or notification
    } catch (error) {
      console.error("SSH command failed:", error);
    }
  };

  const restartService = async (service: Service) => {
    if (!service.container) return;
    
    const node = service.node.toLowerCase();
    const command = `docker restart ${service.container}`;
    await executeSSH(node, command);
    
    // Refresh status after a delay
    setTimeout(refreshStatus, 2000);
  };

  const rebuildService = async (service: Service) => {
    if (!service.container) return;
    
    const node = service.node.toLowerCase();
    const serviceName = service.container.replace("_", "-"); // Convert to compose service name
    const command = `cd /home/misterobots/Home_AI_Lab && docker compose -f turing_gateway/docker-compose.yml build ${serviceName} && docker compose -f turing_gateway/docker-compose.yml up -d ${serviceName}`;
    await executeSSH(node, command);
    
    setTimeout(refreshStatus, 5000);
  };

  useEffect(() => {
    refreshStatus();
    const interval = setInterval(refreshStatus, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--chat-border)]">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-[var(--chat-accent)]" />
          <span className="text-sm font-semibold text-[var(--chat-text)]">DevOps</span>
        </div>
        <button
          onClick={refreshStatus}
          disabled={loading}
          className="p-1 rounded hover:bg-[var(--chat-hover)] transition-colors"
          title="Refresh status"
        >
          <RotateCw 
            size={14} 
            className={`text-[var(--chat-muted)] ${loading ? "animate-spin" : ""}`} 
          />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {/* Pioneer Nodes Section */}
        <section>
          <h3 className="text-xs font-semibold text-[var(--chat-muted)] uppercase mb-2 flex items-center gap-2">
            <Server size={12} />
            Pioneer Nodes
          </h3>
          <div className="space-y-1">
            {nodes.map((node) => (
              <div
                key={node.name}
                className="flex items-center justify-between px-3 py-2 bg-[var(--chat-input-bg)] border border-[var(--chat-border)] rounded hover:border-[var(--chat-accent)] transition-colors"
              >
                <div className="flex items-center gap-2 flex-1">
                  {getStatusIcon(node.status)}
                  <div className="flex flex-col">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-[var(--chat-text)]">
                        {node.name}
                      </span>
                      {node.isLocal && (
                        <span className="px-1.5 py-0.5 text-xs bg-blue-500/20 text-blue-400 rounded">
                          LOCAL
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-[var(--chat-muted)]">{node.ip}</span>
                  </div>
                </div>
                {!node.isLocal && (
                  <button
                    onClick={() => executeSSH(node.name.toLowerCase(), "hostname && uptime")}
                    className="p-1.5 rounded hover:bg-[var(--chat-hover)] transition-colors"
                    title="SSH to node"
                  >
                    <TerminalIcon size={14} className="text-[var(--chat-accent)]" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Services Section */}
        <section>
          <h3 className="text-xs font-semibold text-[var(--chat-muted)] uppercase mb-2 flex items-center gap-2">
            <Play size={12} />
            Services
          </h3>
          <div className="space-y-1">
            {services.map((service) => (
              <div
                key={`${service.node}-${service.name}`}
                className="flex items-center justify-between px-3 py-2 bg-[var(--chat-input-bg)] border border-[var(--chat-border)] rounded hover:border-[var(--chat-accent)] transition-colors"
              >
                <div className="flex items-center gap-2 flex-1">
                  {getStatusIcon(service.status)}
                  <div className="flex flex-col flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-[var(--chat-text)]">{service.name}</span>
                      {service.port && (
                        <span className="text-xs text-[var(--chat-muted)]">:{service.port}</span>
                      )}
                    </div>
                    <span className="text-xs text-[var(--chat-muted)]">{service.node}</span>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  {service.port && (
                    <button
                      onClick={() => window.open(`http://${nodes.find(n => n.name === service.node)?.ip}:${service.port}`, "_blank")}
                      className="p-1.5 rounded hover:bg-[var(--chat-hover)] transition-colors"
                      title="Open in browser"
                    >
                      <ExternalLink size={14} className="text-[var(--chat-muted)]" />
                    </button>
                  )}
                  {service.container && (
                    <>
                      <button
                        onClick={() => restartService(service)}
                        className="p-1.5 rounded hover:bg-[var(--chat-hover)] transition-colors"
                        title="Restart service"
                      >
                        <RotateCw size={14} className="text-[var(--chat-accent)]" />
                      </button>
                      <button
                        onClick={() => rebuildService(service)}
                        className="p-1.5 rounded hover:bg-[var(--chat-hover)] transition-colors"
                        title="Rebuild & restart"
                      >
                        <Play size={14} className="text-green-500" />
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Quick Actions Section */}
        <section>
          <h3 className="text-xs font-semibold text-[var(--chat-muted)] uppercase mb-2">
            Quick Actions
          </h3>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => executeSSH("turing", "cd /home/misterobots/Home_AI_Lab && git pull")}
              className="px-3 py-2 text-xs bg-[var(--chat-input-bg)] hover:bg-[var(--chat-hover)] border border-[var(--chat-border)] rounded transition-colors text-left"
            >
              Git Pull (Turing)
            </button>
            <button
              onClick={() => executeSSH("turing", "docker compose -f /home/misterobots/Home_AI_Lab/turing_gateway/docker-compose.yml restart")}
              className="px-3 py-2 text-xs bg-[var(--chat-input-bg)] hover:bg-[var(--chat-hover)] border border-[var(--chat-border)] rounded transition-colors text-left"
            >
              Restart All Services
            </button>
            <button
              onClick={() => executeSSH("hopper", "docker logs -f postgres")}
              className="px-3 py-2 text-xs bg-[var(--chat-input-bg)] hover:bg-[var(--chat-hover)] border border-[var(--chat-border)] rounded transition-colors text-left"
            >
              View PostgreSQL Logs
            </button>
            <button
              onClick={() => executeSSH("turing", "docker logs -f agent_runtime")}
              className="px-3 py-2 text-xs bg-[var(--chat-input-bg)] hover:bg-[var(--chat-hover)] border border-[var(--chat-border)] rounded transition-colors text-left"
            >
              View Agent Runtime Logs
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
