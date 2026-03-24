import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// Server-side Grafana URL — reachable from the hive-ui container on the LAN.
// The browser never sees this address; it only talks to /api/grafana/*.
const GRAFANA_URL =
  process.env.GRAFANA_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_GRAFANA_URL ||
  "http://192.168.2.103/grafana";

async function proxyGrafana(req: NextRequest) {
  const url = new URL(req.url);
  // Strip the /api/grafana prefix to get the real Grafana path
  const grafanaPath = url.pathname.replace(/^\/api\/grafana/, "");
  const target = `${GRAFANA_URL}${grafanaPath}${url.search}`;

  // Forward most headers, skip host/connection
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

  const contentType = upstream.headers.get("Content-Type") || "text/html";
  const cacheControl = upstream.headers.get("Cache-Control") || "no-cache";

  // For HTML responses, rewrite the <base href> tag so the browser resolves
  // Grafana's relative asset paths through /api/grafana/ instead of /grafana/.
  if (contentType.includes("text/html")) {
    let html = await upstream.text();
    html = html.replace(
      /<base\s+href="\/grafana\/"\s*\/?>/,
      '<base href="/api/grafana/" />'
    );
    return new Response(html, {
      status: upstream.status,
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "no-cache",
      },
    });
  }

  // Non-HTML: pass through as-is (JS, CSS, images, JSON API responses)
  const body = await upstream.arrayBuffer();
  return new Response(body, {
    status: upstream.status,
    headers: {
      "Content-Type": contentType,
      "Cache-Control": cacheControl,
    },
  });
}

export async function GET(req: NextRequest) {
  return proxyGrafana(req);
}

export async function POST(req: NextRequest) {
  return proxyGrafana(req);
}
