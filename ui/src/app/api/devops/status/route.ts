import { NextRequest, NextResponse } from "next/server";
import { Socket } from "node:net";

type ServiceStatus = "running" | "stopped" | "error" | "unknown";

const NODES = {
  lovelace: { ip: "192.168.2.101", isLocal: true },
  turing: { ip: "192.168.2.103", isLocal: false },
  hopper: { ip: "192.168.2.102", isLocal: false },
} as const;

const SERVICES = [
  { name: "Agent Runtime", container: "agent_runtime", node: "turing", port: 8008 },
  { name: "Memex UI", container: "memex_ui", node: "turing", port: 3200 },
  { name: "Ollama (Turing)", container: "ollama-turing", node: "turing", port: 11434 },
  { name: "PostgreSQL", container: "postgres", node: "hopper", port: 5432 },
  { name: "Redis", container: "redis", node: "hopper", port: 6379 },
  { name: "Langfuse", container: "langfuse", node: "hopper", port: 3000 },
  { name: "Ollama (Lovelace)", container: "ollama", node: "lovelace", port: 11434 },
] as const;

function isAdmin(request: NextRequest) {
  const groups = request.headers.get("x-authentik-groups") ?? "";
  return ["memex-admin", "authentik Admins"].some((group) => groups.includes(group));
}

function probePort(host: string, port: number, timeoutMs = 1500): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = new Socket();
    const finish = (result: boolean) => {
      socket.removeAllListeners();
      socket.destroy();
      resolve(result);
    };
    socket.setTimeout(timeoutMs);
    socket.once("connect", () => finish(true));
    socket.once("timeout", () => finish(false));
    socket.once("error", () => finish(false));
    socket.connect(port, host);
  });
}

export async function GET(request: NextRequest) {
  if (!isAdmin(request)) return NextResponse.json({ error: "Administrator access required" }, { status: 403 });

  const services = await Promise.all(SERVICES.map(async (service) => {
    const node = NODES[service.node];
    const reachable = await probePort(node.ip, service.port);
    return { ...service, node: service.node[0].toUpperCase() + service.node.slice(1), status: reachable ? "running" : "stopped" as ServiceStatus };
  }));
  const nodes = Object.entries(NODES).map(([name, node]) => ({
    name: name[0].toUpperCase() + name.slice(1),
    ip: node.ip,
    isLocal: node.isLocal,
    status: services.some((service) => service.node.toLowerCase() === name && service.status === "running") ? "online" : "offline",
  }));

  return NextResponse.json({ nodes, services, checkedAt: new Date().toISOString() });
}
