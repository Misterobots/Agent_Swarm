import { NextRequest, NextResponse } from "next/server";

const PIONEER_NODES = {
  lovelace: { ip: "192.168.2.101", isLocal: true },
  turing: { ip: "192.168.2.103", isLocal: false },
  hopper: { ip: "192.168.2.102", isLocal: false },
  bmo: { ip: "192.168.2.106", isLocal: false },
};

const SERVICES = [
  { name: "Agent Runtime", container: "agent_runtime", node: "turing", port: 5001 },
  { name: "Memex UI", container: "hive_ui", node: "turing", port: 3000 },
  { name: "PostgreSQL", container: "postgres", node: "hopper", port: 5432 },
  { name: "Redis", container: "redis", node: "hopper", port: 6379 },
  { name: "Langfuse", container: "langfuse", node: "hopper", port: 3001 },
  { name: "Ollama", container: "ollama", node: "turing", port: 11434 },
  { name: "Ollama (Lovelace)", node: "lovelace", port: 11434 },
];

async function checkNodeStatus(node: string, ip: string): Promise<"online" | "offline"> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2000);
    
    // Try to ping the node (you might need to adjust this based on your setup)
    const response = await fetch(`http://${ip}:11434/api/tags`, {
      signal: controller.signal,
    }).catch(() => null);
    
    clearTimeout(timeout);
    return response?.ok ? "online" : "offline";
  } catch {
    return "offline";
  }
}

async function checkServiceStatus(
  service: typeof SERVICES[0]
): Promise<"running" | "stopped" | "error" | "unknown"> {
  const node = PIONEER_NODES[service.node as keyof typeof PIONEER_NODES];
  if (!node) return "unknown";

  // If it's a service without a container (like Ollama on Lovelace), just check the port
  if (!service.container) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 1000);
      
      const response = await fetch(`http://${node.ip}:${service.port}`, {
        signal: controller.signal,
      }).catch(() => null);
      
      clearTimeout(timeout);
      return response ? "running" : "stopped";
    } catch {
      return "stopped";
    }
  }

  // For containerized services, we'd need to SSH and check docker ps
  // For now, return unknown - this will be implemented with the SSH endpoint
  return "unknown";
}

export async function GET(request: NextRequest) {
  try {
    // Check node status
    const nodeChecks = await Promise.all(
      Object.entries(PIONEER_NODES).map(async ([name, { ip, isLocal }]) => ({
        name: name.charAt(0).toUpperCase() + name.slice(1),
        ip,
        status: await checkNodeStatus(name, ip),
        isLocal,
      }))
    );

    // Check service status
    const serviceChecks = await Promise.all(
      SERVICES.map(async (service) => ({
        ...service,
        status: await checkServiceStatus(service),
      }))
    );

    return NextResponse.json({
      nodes: nodeChecks,
      services: serviceChecks,
    });
  } catch (error) {
    console.error("DevOps status check failed:", error);
    return NextResponse.json(
      { error: "Failed to check status" },
      { status: 500 }
    );
  }
}
