import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const LANGFUSE_URL = process.env.LANGFUSE_URL || "http://control-node:3000";
const LF_PUBLIC = process.env.LANGFUSE_PUBLIC_KEY || "";
const LF_SECRET = process.env.LANGFUSE_SECRET_KEY || "";

async function proxyRequest(req: NextRequest) {
  const url = new URL(req.url);
  const langfusePath = url.pathname.replace(/^\/api\/langfuse/, "");
  const target = `${LANGFUSE_URL}/api/public${langfusePath}${url.search}`;

  const headers = new Headers();
  headers.set(
    "Content-Type",
    req.headers.get("Content-Type") || "application/json"
  );

  // Inject Basic Auth server-side so credentials never reach the browser
  if (LF_PUBLIC && LF_SECRET) {
    const encoded = Buffer.from(`${LF_PUBLIC}:${LF_SECRET}`).toString(
      "base64"
    );
    headers.set("Authorization", `Basic ${encoded}`);
  }

  const init: RequestInit = {
    method: req.method,
    headers,
  };

  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.text();
  }

  try {
    const upstream = await fetch(target, init);
    const body = await upstream.text();
    return new Response(body, {
      status: upstream.status,
      headers: {
        "Content-Type":
          upstream.headers.get("Content-Type") || "application/json",
      },
    });
  } catch {
    return new Response(
      JSON.stringify({ error: "Langfuse unreachable" }),
      { status: 502, headers: { "Content-Type": "application/json" } }
    );
  }
}

export async function GET(req: NextRequest) {
  return proxyRequest(req);
}

export async function POST(req: NextRequest) {
  return proxyRequest(req);
}
