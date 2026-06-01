import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";

const SSH_BINARY = "C:\\Windows\\System32\\OpenSSH\\ssh.exe";
const SSH_USER = "misterobots";

const NODE_IPS: Record<string, string> = {
  turing: "192.168.2.103",
  hopper: "192.168.2.102",
  lovelace: "192.168.2.101",
  bmo: "192.168.2.106",
};

const REPO_PATHS: Record<string, string> = {
  lovelace: "C:\\Users\\panca\\OneDrive\\Documents\\GitHub\\Agent_Swarm",
  turing: "/home/misterobots/Home_AI_Lab",
  hopper: "/home/misterobots/Agent_Swarm",
  bmo: "/home/misterobots/Agent_Swarm",
};

const DANGEROUS_PATH_RE = /(\.\.|[\0;|&$`])/;

function validateFilePaths(files: unknown[]): string | null {
  for (const f of files) {
    if (typeof f !== "string") return "All file paths must be strings";
    if (DANGEROUS_PATH_RE.test(f))
      return `Unsafe path rejected: ${f}`;
  }
  return null;
}

async function executeGitStage(
  node: string,
  files: string[]
): Promise<{ stdout: string; stderr: string; exitCode: number }> {
  return new Promise((resolve, reject) => {
    const ip = NODE_IPS[node];
    const repoPath = REPO_PATHS[node];

    if (!ip || !repoPath) {
      reject(new Error(`Unknown node: ${node}`));
      return;
    }

    // Quote each file path to handle spaces
    const quotedFiles = files.map((f) => `"${f}"`).join(" ");

    if (node === "lovelace") {
      const command = `git -C "${repoPath}" add -- ${quotedFiles}`;
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

    // Remote nodes via SSH
    const command = `git -C "${repoPath}" add -- ${quotedFiles}`;
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
    const { node, files } = await request.json();

    if (!node) {
      return NextResponse.json({ error: "Missing node" }, { status: 400 });
    }

    if (!Array.isArray(files) || files.length === 0) {
      return NextResponse.json(
        { error: "files must be a non-empty array" },
        { status: 400 }
      );
    }

    const validationError = validateFilePaths(files);
    if (validationError) {
      return NextResponse.json({ error: validationError }, { status: 400 });
    }

    const result = await executeGitStage(node, files as string[]);

    return NextResponse.json({
      success: result.exitCode === 0,
      stdout: result.stdout,
      stderr: result.stderr,
      exitCode: result.exitCode,
    });
  } catch (error) {
    console.error("Git stage failed:", error);
    return NextResponse.json(
      { error: "Git stage failed", details: String(error) },
      { status: 500 }
    );
  }
}
