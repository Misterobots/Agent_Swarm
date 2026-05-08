import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// maintenance_router runs on the gateway node alongside Alertmanager.
// The browser only ever talks to /api/maintenance/* — this proxy forwards
// to the LAN address, never exposing it to the client.
const ROUTER_URL =
  process.env.MAINTENANCE_ROUTER_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_MAINTENANCE_ROUTER_URL ||
  "http://maintenance-router:9095";

async function proxy(req: NextRequest) {
  const url = new URL(req.url);
  const upstreamPath = url.pathname.replace(/^\/api\/maintenance/, "");
  const target = `${ROUTER_URL}${upstreamPath}${url.search}`;

  const headers = new Headers();
  for (const [key, value] of req.headers.entries()) {
    if (
      !["host", "connection", "transfer-encoding"].includes(key.toLowerCase())
    ) {
      headers.set(key, value);
    }
  }

  const init: RequestInit = {
    method: req.method,
    headers,
    redirect: "follow",
  };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.arrayBuffer();
  }

  const upstream = await fetch(target, init);
  const body = await upstream.arrayBuffer();
  return new Response(body, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") || "application/json",
      "Cache-Control": "no-cache",
    },
  });
}

export async function GET(req: NextRequest) {
  return proxy(req);
}

export async function POST(req: NextRequest) {
  return proxy(req);
}
