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
      // Run real git status inside the dev_sandbox container
      const result = await new Promise<{ stdout: string; stderr: string; exitCode: number }>(
        (resolve, reject) => {
          const proc = spawn("docker", [
            "exec",
            "dev_sandbox",
            "sh",
            "-c",
            "cd /workspace && git status -b --porcelain",
          ]);

          let stdout = "";
          let stderr = "";

          proc.stdout.on("data", (data) => { stdout += data.toString(); });
          proc.stderr.on("data", (data) => { stderr += data.toString(); });
          proc.on("close", (code) => { resolve({ stdout, stderr, exitCode: code || 0 }); });
          proc.on("error", (err) => { reject(err); });
        }
      );

      if (result.exitCode !== 0) {
        return NextResponse.json(
          { error: `dev_sandbox container error: ${result.stderr || "container may not be running"}` },
          { status: 500 }
        );
      }

      const wsLines = result.stdout.split("\n");
      const wsBranchLine = wsLines[0] || "";
      const wsBranch = wsBranchLine.match(/## ([^\s.]+)/)?.[1] || "unknown";

      const wsAheadMatch = wsBranchLine.match(/\[ahead (\d+)/);
      const wsBehindMatch = wsBranchLine.match(/behind (\d+)/);
      const wsAhead = wsAheadMatch ? parseInt(wsAheadMatch[1]) : 0;
      const wsBehind = wsBehindMatch ? parseInt(wsBehindMatch[1]) : 0;

      const wsModified: string[] = [];
      const wsAdded: string[] = [];
      const wsDeleted: string[] = [];
      const wsUntracked: string[] = [];

      for (let i = 1; i < wsLines.length; i++) {
        const line = wsLines[i].trim();
        if (!line) continue;
        const status = line.substring(0, 2);
        const file = line.substring(3);
        if (status.includes("M")) wsModified.push(file);
        if (status.includes("A")) wsAdded.push(file);
        if (status.includes("D")) wsDeleted.push(file);
        if (status.includes("?")) wsUntracked.push(file);
      }

      return NextResponse.json({
        branch: wsBranch,
        ahead: wsAhead,
        behind: wsBehind,
        modified: wsModified,
        added: wsAdded,
        deleted: wsDeleted,
        untracked: wsUntracked,
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

    const aheadMatch = branchLine.match(/\[ahead (\d+)/);
    const behindMatch = branchLine.match(/behind (\d+)/);
    const ahead = aheadMatch ? parseInt(aheadMatch[1]) : 0;
    const behind = behindMatch ? parseInt(behindMatch[1]) : 0;

    return NextResponse.json({
      branch,
      ahead,
      behind,
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
