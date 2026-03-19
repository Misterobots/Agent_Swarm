import { NextRequest } from "next/server";

const BACKEND_URL = process.env.API_BASE_URL || "http://localhost:8000";

async function proxyRequest(req: NextRequest) {
  const url = new URL(req.url);
  // Strip /api/backend prefix to get the real path
  const backendPath = url.pathname.replace(/^\/api\/backend/, "");
  const target = `${BACKEND_URL}${backendPath}${url.search}`;

  const headers = new Headers();
  headers.set("Content-Type", req.headers.get("Content-Type") || "application/json");
  // Forward accept header for SSE
  if (req.headers.get("Accept")) {
    headers.set("Accept", req.headers.get("Accept")!);
  }

  const init: RequestInit = {
    method: req.method,
    headers,
  };

  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.text();
  }

  const upstream = await fetch(target, init);

  // If the response is SSE, stream it through directly
  if (
    upstream.headers.get("content-type")?.includes("text/event-stream") ||
    upstream.headers.get("transfer-encoding") === "chunked"
  ) {
    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  }

  // Non-streaming: forward as-is
  const body = await upstream.text();
  return new Response(body, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") || "application/json",
    },
  });
}

export async function GET(req: NextRequest) {
  return proxyRequest(req);
}

export async function POST(req: NextRequest) {
  return proxyRequest(req);
}
