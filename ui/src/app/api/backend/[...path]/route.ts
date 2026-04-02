import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 300; // Allow long-running streaming responses

const BACKEND_URL = process.env.API_BASE_URL || "http://localhost:8000";

async function proxyRequest(req: NextRequest) {
  const url = new URL(req.url);
  const backendPath = url.pathname.replace(/^\/api\/backend/, "");
  const target = `${BACKEND_URL}${backendPath}${url.search}`;

  const headers = new Headers();
  headers.set("Content-Type", req.headers.get("Content-Type") || "application/json");

  const init: RequestInit = {
    method: req.method,
    headers,
  };

  let bodyText = "";
  if (req.method !== "GET" && req.method !== "HEAD") {
    bodyText = await req.text();
    init.body = bodyText;
  }

  // Detect if this is a streaming request from the body
  let wantsStream = false;
  try {
    if (bodyText) {
      const parsed = JSON.parse(bodyText);
      wantsStream = parsed.stream === true;
    }
  } catch {
    // not JSON, that's fine
  }

  // Chat streaming can legitimately run longer than a minute; keep non-stream calls tighter.
  const timeoutMs = wantsStream ? 300_000 : 55_000;
  const upstream = await fetch(target, {
    ...init,
    signal: AbortSignal.timeout(timeoutMs),
  });

  const isSSE =
    upstream.headers.get("content-type")?.includes("text/event-stream") ||
    wantsStream;

  if (isSSE && upstream.body) {
    // Manually read from the upstream and push to a new ReadableStream
    // to avoid compatibility issues with piping between fetch implementations
    const reader = upstream.body.getReader();
    const stream = new ReadableStream({
      async pull(controller) {
        try {
          const { done, value } = await reader.read();
          if (done) {
            controller.close();
            return;
          }
          controller.enqueue(value);
        } catch (err) {
          console.error("[api/backend] SSE relay failed", {
            target,
            method: req.method,
            timeoutMs,
            error: err instanceof Error ? err.message : String(err),
          });
          controller.error(err);
        }
      },
      cancel() {
        reader.cancel();
      },
    });

    return new Response(stream, {
      status: upstream.status,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  }

  // Non-streaming: pipe body directly (preserves binary files like GLB/STL)
  const contentType = upstream.headers.get("Content-Type") || "application/json";
  const responseHeaders: Record<string, string> = { "Content-Type": contentType };
  const contentLength = upstream.headers.get("Content-Length");
  if (contentLength) responseHeaders["Content-Length"] = contentLength;

  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export async function GET(req: NextRequest) {
  return proxyRequest(req);
}

export async function POST(req: NextRequest) {
  return proxyRequest(req);
}
