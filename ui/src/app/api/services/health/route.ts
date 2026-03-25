import { NextResponse } from "next/server";
import { createConnection } from "net";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND_URL = process.env.API_BASE_URL || "http://localhost:8000";
const CONTROL_IP = process.env.CONTROL_NODE_IP || "control-node";

interface ServiceCheck {
  name: string;
  port: number;
  httpPath?: string;
}

const CONTROL_PLANE_SERVICES: ServiceCheck[] = [
  { name: "Langfuse", port: 3000, httpPath: "/api/public/health" },
  { name: "MinIO API", port: 9190, httpPath: "/minio/health/live" },
  { name: "PostgreSQL", port: 5432 },
  { name: "SPIRE Server", port: 8081 },
];

async function checkHTTP(
  host: string,
  port: number,
  path: string
): Promise<boolean> {
  try {
    const res = await fetch(`http://${host}:${port}${path}`, {
      signal: AbortSignal.timeout(3000),
    });
    return res.status < 500;
  } catch {
    return false;
  }
}

function checkTCP(host: string, port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = createConnection({ host, port, timeout: 3000 });
    socket.on("connect", () => {
      socket.destroy();
      resolve(true);
    });
    socket.on("timeout", () => {
      socket.destroy();
      resolve(false);
    });
    socket.on("error", () => {
      resolve(false);
    });
  });
}

export async function GET() {
  // Fetch node health from backend
  let nodes = [];
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/health/nodes`, {
      signal: AbortSignal.timeout(5000),
    });
    if (res.ok) {
      const data = await res.json();
      nodes = data.nodes || data || [];
    }
  } catch {
    // Backend unreachable
  }

  // Check control plane services in parallel
  const controlPlane = await Promise.all(
    CONTROL_PLANE_SERVICES.map(async (svc) => {
      const start = Date.now();
      let healthy: boolean;
      if (svc.httpPath) {
        healthy = await checkHTTP(CONTROL_IP, svc.port, svc.httpPath);
      } else {
        healthy = await checkTCP(CONTROL_IP, svc.port);
      }
      return {
        name: svc.name,
        status: healthy ? ("healthy" as const) : ("down" as const),
        port: svc.port,
        latency: Date.now() - start,
      };
    })
  );

  return NextResponse.json({
    nodes,
    controlPlane,
    containers: [], // populated later if Docker socket access is added
    timestamp: Date.now(),
  });
}
