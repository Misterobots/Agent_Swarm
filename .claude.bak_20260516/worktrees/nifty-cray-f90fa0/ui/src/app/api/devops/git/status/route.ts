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

async function executeGitCommand(
  node: string,
  gitCommand: string
): Promise<{ stdout: string; stderr: string; exitCode: number }> {
  return new Promise((resolve, reject) => {
    const ip = NODE_IPS[node];
    const repoPath = REPO_PATHS[node];

    if (!ip || !repoPath) {
      reject(new Error(`Unknown node: ${node}`));
      return;
    }

    const command = `cd ${repoPath} && git ${gitCommand}`;

    // For Lovelace (local), use PowerShell
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

    // For remote nodes, use SSH
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

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const node = searchParams.get("node") || "workspace";

    if (node === "workspace") {
      // For workspace, return local git status
      return NextResponse.json({
        branch: "main",
        ahead: 0,
        behind: 0,
        modified: [],
        added: [],
        deleted: [],
        untracked: [],
      });
    }

    const result = await executeGitCommand(node, "status --porcelain -b");

    // Parse git status output
    const lines = result.stdout.split("\n");
    const branchLine = lines[0];
    const branch = branchLine.match(/## ([^\s.]+)/)?.[1] || "main";
    
    const modified: string[] = [];
    const added: string[] = [];
    const deleted: string[] = [];
    const untracked: string[] = [];

    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;

      const status = line.substring(0, 2);
      const file = line.substring(3);

      if (status.includes("M")) modified.push(file);
      if (status.includes("A")) added.push(file);
      if (status.includes("D")) deleted.push(file);
      if (status.includes("?")) untracked.push(file);
    }

    return NextResponse.json({
      branch,
      ahead: 0, // TODO: Parse ahead/behind from branch line
      behind: 0,
      modified,
      added,
      deleted,
      untracked,
    });
  } catch (error) {
    console.error("Git status failed:", error);
    return NextResponse.json(
      { error: "Failed to get git status" },
      { status: 500 }
    );
  }
}
