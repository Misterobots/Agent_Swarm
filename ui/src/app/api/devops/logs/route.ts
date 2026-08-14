import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";

const SSH_BINARY = process.env.MEMEX_SSH_BINARY ?? "ssh";
const SSH_USER = "misterobots";

const NODE_IPS: Record<string, string> = {
  turing: "192.168.2.103",
  hopper: "192.168.2.102",
};

const CONTAINER_NODES: Record<string, string> = {
  agent_runtime: "turing",
  hive_ui: "turing",
  postgres: "hopper",
  redis: "hopper",
  langfuse: "hopper",
  ollama: "turing",
};

async function fetchDockerLogs(
  source: string,
  lines: number = 100
): Promise<string> {
  return new Promise((resolve, reject) => {
    const node = CONTAINER_NODES[source];
    if (!node) {
      reject(new Error(`Unknown source: ${source}`));
      return;
    }

    const ip = NODE_IPS[node];
    const command = `docker logs --tail ${lines} ${source}`;

    const proc = spawn(SSH_BINARY, [
      "-o",
      "StrictHostKeyChecking=no",
      "-o",
      "BatchMode=yes",
      `${SSH_USER}@${ip}`,
      command,
    ]);

    let output = "";

    proc.stdout.on("data", (data) => {
      output += data.toString();
    });

    proc.stderr.on("data", (data) => {
      output += data.toString();
    });

    proc.on("close", (code) => {
      if (code === 0) {
        resolve(output);
      } else {
        reject(new Error(`Docker logs failed with exit code ${code}`));
      }
    });

    proc.on("error", (err) => {
      reject(err);
    });
  });
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const sources = searchParams.get("sources")?.split(",") || [];
    const limit = parseInt(searchParams.get("limit") || "100", 10);

    if (sources.length === 0) {
      return NextResponse.json({ logs: [] });
    }

    const logPromises = sources.map(async (source) => {
      try {
        const output = await fetchDockerLogs(source, limit);
        const lines = output.split("\n").filter((line) => line.trim());

        return lines.map((line) => ({
          timestamp: new Date().toISOString(),
          level: detectLogLevel(line),
          source,
          message: line,
        }));
      } catch (error) {
        console.error(`Failed to fetch logs for ${source}:`, error);
        return [];
      }
    });

    const allLogs = (await Promise.all(logPromises)).flat();

    // Sort by timestamp (newest first)
    allLogs.sort(
      (a, b) =>
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );

    return NextResponse.json({ logs: allLogs.slice(0, limit) });
  } catch (error) {
    console.error("Failed to fetch logs:", error);
    return NextResponse.json(
      { error: "Failed to fetch logs" },
      { status: 500 }
    );
  }
}

function detectLogLevel(line: string): "ERROR" | "WARN" | "INFO" | "DEBUG" {
  const upperLine = line.toUpperCase();
  if (upperLine.includes("ERROR") || upperLine.includes("FATAL"))
    return "ERROR";
  if (upperLine.includes("WARN")) return "WARN";
  if (upperLine.includes("DEBUG")) return "DEBUG";
  return "INFO";
}
