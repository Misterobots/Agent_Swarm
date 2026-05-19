import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";

const SSH_BINARY = "C:\\Windows\\System32\\OpenSSH\\ssh.exe";
const SSH_USER = "misterobots";

const NODE_IPS: Record<string, string> = {
  turing: "192.168.2.103",
  hopper: "192.168.2.102",
  lovelace: "192.168.2.101",
};

const REPO_PATHS: Record<string, string> = {
  lovelace: "C:\\Users\\panca\\OneDrive\\Documents\\GitHub\\Agent_Swarm",
  turing: "/home/misterobots/Home_AI_Lab",
  hopper: "/home/misterobots/Agent_Swarm",
};

async function executeGitPull(node: string): Promise<{ stdout: string; stderr: string; exitCode: number }> {
  return new Promise((resolve, reject) => {
    const ip = NODE_IPS[node];
    const repoPath = REPO_PATHS[node];

    if (!ip || !repoPath) {
      reject(new Error(`Unknown node: ${node}`));
      return;
    }

    const command = `cd ${repoPath} && git pull`;

    if (node === "lovelace") {
      const proc = spawn("powershell.exe", ["-Command", command]);

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

    const proc = spawn(SSH_BINARY, [
      "-o",
      "StrictHostKeyChecking=no",
      "-o",
      "BatchMode=yes",
      `${SSH_USER}@${ip}`,
      command,
    ]);

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
    const { node } = await request.json();

    if (!node) {
      return NextResponse.json({ error: "Missing node" }, { status: 400 });
    }

    const result = await executeGitPull(node);

    return NextResponse.json({
      success: result.exitCode === 0,
      stdout: result.stdout,
      stderr: result.stderr,
      exitCode: result.exitCode,
    });
  } catch (error) {
    console.error("Git pull failed:", error);
    return NextResponse.json(
      { error: "Git pull failed", details: String(error) },
      { status: 500 }
    );
  }
}
