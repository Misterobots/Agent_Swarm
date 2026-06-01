import { NextRequest } from "next/server";
import { spawn } from "child_process";

// Allowlist of container names that may be streamed
const ALLOWED_SOURCES = new Set([
  "agent_runtime",
  "memex_ui",
  "traefik",
  "cloudflared",
  "ollama-turing",
  "redis-turing",
  "dev_sandbox",
  // Hopper containers
  "postgres",
  "redis",
  "langfuse",
  // Lovelace containers
  "ollama",
]);

// Map each source to its default node when the caller omits ?node=
const SOURCE_DEFAULT_NODE: Record<string, string> = {
  agent_runtime: "turing",
  memex_ui: "turing",
  traefik: "turing",
  cloudflared: "turing",
  "ollama-turing": "turing",
  "redis-turing": "turing",
  dev_sandbox: "lovelace",
  postgres: "hopper",
  redis: "hopper",
  langfuse: "hopper",
  ollama: "lovelace",
};

const NODE_IPS: Record<string, string> = {
  turing: "192.168.2.103",
  hopper: "192.168.2.102",
  bmo: "192.168.2.106",
  lovelace: "192.168.2.101",
  workspace: "192.168.2.101", // alias for lovelace
};

const SSH_USER = "misterobots";

const SSH_BINARY =
  process.platform === "win32"
    ? require("fs").existsSync("C:\\Windows\\System32\\OpenSSH\\ssh.exe")
      ? "C:\\Windows\\System32\\OpenSSH\\ssh.exe"
      : "ssh"
    : "ssh";

// Heuristic: detect log level from a raw log line
function detectLevel(line: string): "INFO" | "WARN" | "ERROR" | "DEBUG" {
  const upper = line.toUpperCase();
  if (upper.includes("ERROR") || upper.includes("CRITICAL") || upper.includes("FATAL")) return "ERROR";
  if (upper.includes("WARN") || upper.includes("WARNING")) return "WARN";
  if (upper.includes("DEBUG") || upper.includes("TRACE")) return "DEBUG";
  return "INFO";
}

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const source = searchParams.get("source") ?? "agent_runtime";
  const nodeParam = (searchParams.get("node") ?? "").toLowerCase();

  // Security: validate source against allowlist
  if (!ALLOWED_SOURCES.has(source)) {
    return new Response(
      JSON.stringify({ error: `Unknown source: ${source}. Allowed: ${[...ALLOWED_SOURCES].join(", ")}` }),
      { status: 400, headers: { "Content-Type": "application/json" } }
    );
  }

  // Resolve node: explicit param > default from source map > lovelace
  const resolvedNode =
    nodeParam && NODE_IPS[nodeParam]
      ? nodeParam
      : SOURCE_DEFAULT_NODE[source] ?? "lovelace";

  const isLocal = resolvedNode === "lovelace" || resolvedNode === "workspace";

  const stream = new ReadableStream({
    start(controller) {
      const enc = new TextEncoder();

      const send = (line: string) => {
        const trimmed = line.trim();
        if (!trimmed) return;
        const event =
          "data: " +
          JSON.stringify({
            ts: new Date().toISOString(),
            level: detectLevel(trimmed),
            source,
            message: trimmed,
          }) +
          "\n\n";
        try {
          controller.enqueue(enc.encode(event));
        } catch {
          // controller may be closed already — ignore
        }
      };

      let child: ReturnType<typeof spawn>;

      if (isLocal) {
        // Local docker command (Lovelace / workspace)
        child = spawn("docker", ["logs", "-f", "--tail", "50", source], {
          shell: false,
        });
      } else {
        // Remote node via SSH
        const ip = NODE_IPS[resolvedNode];
        child = spawn(
          SSH_BINARY,
          [
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            `${SSH_USER}@${ip}`,
            `docker logs -f --tail 50 ${source}`,
          ],
          { shell: false }
        );
      }

      let stdoutBuf = "";
      let stderrBuf = "";

      child.stdout.on("data", (chunk: Buffer) => {
        stdoutBuf += chunk.toString();
        const lines = stdoutBuf.split("\n");
        stdoutBuf = lines.pop() ?? "";
        lines.forEach(send);
      });

      child.stderr.on("data", (chunk: Buffer) => {
        stderrBuf += chunk.toString();
        const lines = stderrBuf.split("\n");
        stderrBuf = lines.pop() ?? "";
        lines.forEach(send);
      });

      child.on("close", () => {
        // Flush any remaining buffer content
        if (stdoutBuf.trim()) send(stdoutBuf);
        if (stderrBuf.trim()) send(stderrBuf);
        try {
          controller.close();
        } catch {
          // ignore if already closed
        }
      });

      child.on("error", (err: Error) => {
        const errEvent =
          "data: " +
          JSON.stringify({
            ts: new Date().toISOString(),
            level: "ERROR",
            source,
            message: `Stream error: ${err.message}`,
          }) +
          "\n\n";
        try {
          controller.enqueue(enc.encode(errEvent));
          controller.close();
        } catch {
          // ignore
        }
      });

      // Kill child when client disconnects
      request.signal.addEventListener("abort", () => {
        try {
          child.kill();
        } catch {
          // ignore if already exited
        }
        try {
          controller.close();
        } catch {
          // ignore
        }
      });
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no", // disable nginx/traefik buffering
    },
  });
}
