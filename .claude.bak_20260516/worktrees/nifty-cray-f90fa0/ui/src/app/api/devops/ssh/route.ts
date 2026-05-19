import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";

const SSH_BINARY = "C:\\Windows\\System32\\OpenSSH\\ssh.exe";
const SSH_USER = "misterobots";

const NODE_IPS: Record<string, string> = {
  turing: "192.168.2.103",
  hopper: "192.168.2.102",
  bmo: "192.168.2.106",
  lovelace: "192.168.2.101",
};

async function executeSSH(node: string, command: string): Promise<{ stdout: string; stderr: string; exitCode: number }> {
  return new Promise((resolve, reject) => {
    const ip = NODE_IPS[node];
    if (!ip) {
      reject(new Error(`Unknown node: ${node}`));
      return;
    }

    // For Lovelace (local machine), execute directly
    if (node === "lovelace") {
      const proc = spawn("powershell.exe", ["-Command", command], {
        shell: true,
      });

      let stdout = "";
      let stderr = "";

      proc.stdout.on("data", (data) => {
        stdout += data.toString();
      });

      proc.stderr.on("data", (data) => {
        stderr += data.toString();
      });

      proc.on("close", (code) => {
        resolve({ stdout, stderr, exitCode: code || 0 });
      });

      proc.on("error", (err) => {
        reject(err);
      });

      return;
    }

    // For remote nodes, use SSH
    const proc = spawn(
      SSH_BINARY,
      [
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "BatchMode=yes",
        `${SSH_USER}@${ip}`,
        command,
      ],
      {
        shell: false,
      }
    );

    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (data) => {
      stdout += data.toString();
    });

    proc.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    proc.on("close", (code) => {
      resolve({ stdout, stderr, exitCode: code || 0 });
    });

    proc.on("error", (err) => {
      reject(err);
    });
  });
}

export async function POST(request: NextRequest) {
  try {
    const { node, command } = await request.json();

    if (!node || !command) {
      return NextResponse.json(
        { error: "Missing node or command" },
        { status: 400 }
      );
    }

    const result = await executeSSH(node, command);

    return NextResponse.json({
      success: result.exitCode === 0,
      stdout: result.stdout,
      stderr: result.stderr,
      exitCode: result.exitCode,
    });
  } catch (error) {
    console.error("SSH execution failed:", error);
    return NextResponse.json(
      { error: "SSH execution failed", details: String(error) },
      { status: 500 }
    );
  }
}
