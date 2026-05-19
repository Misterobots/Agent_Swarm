"use client";

import { useState, useEffect } from "react";
import { 
  GitBranch, 
  GitCommit, 
  GitPullRequest, 
  Upload, 
  Download, 
  RefreshCw,
  FileText,
  Plus,
  Minus,
  CheckCircle,
  Circle,
  AlertCircle,
  ExternalLink,
  Wifi
} from "lucide-react";
import { useDevStore } from "@/lib/stores/dev-store";

interface GitStatus {
  branch: string;
  ahead: number;
  behind: number;
  modified: string[];
  added: string[];
  deleted: string[];
  untracked: string[];
}

interface RemoteTunnelStatus {
  connected: boolean;
  url?: string;
  error?: string;
}

export function GitPanel() {
  const { selectedNode } = useDevStore();
  const [status, setStatus] = useState<GitStatus>({
    branch: "main",
    ahead: 0,
    behind: 0,
    modified: [],
    added: [],
    deleted: [],
    untracked: [],
  });
  const [commitMessage, setCommitMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [remoteTunnel, setRemoteTunnel] = useState<RemoteTunnelStatus>({
    connected: false,
  });

  const refreshGitStatus = async () => {
    setLoading(true);
    try {
      const response = await fetch(`/api/devops/git/status?node=${selectedNode}`);
      if (response.ok) {
        const data = await response.json();
        setStatus(data);
      }
    } catch (error) {
      console.error("Failed to refresh git status:", error);
    } finally {
      setLoading(false);
    }
  };

  const checkRemoteTunnel = async () => {
    try {
      const response = await fetch("/api/devops/git/tunnel");
      if (response.ok) {
        const data = await response.json();
        setRemoteTunnel(data);
      }
    } catch (error) {
      console.error("Failed to check remote tunnel:", error);
    }
  };

  const connectRemoteTunnel = async () => {
    try {
      setLoading(true);
      const response = await fetch("/api/devops/git/tunnel/connect", {
        method: "POST",
      });
      if (response.ok) {
        const data = await response.json();
        setRemoteTunnel({ connected: true, url: data.url });
      }
    } catch (error) {
      console.error("Failed to connect remote tunnel:", error);
      setRemoteTunnel({ connected: false, error: String(error) });
    } finally {
      setLoading(false);
    }
  };

  const gitPull = async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/devops/git/pull", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ node: selectedNode }),
      });
      if (response.ok) {
        await refreshGitStatus();
      }
    } catch (error) {
      console.error("Git pull failed:", error);
    } finally {
      setLoading(false);
    }
  };

  const gitPush = async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/devops/git/push", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ node: selectedNode }),
      });
      if (response.ok) {
        await refreshGitStatus();
      }
    } catch (error) {
      console.error("Git push failed:", error);
    } finally {
      setLoading(false);
    }
  };

  const gitCommit = async () => {
    if (!commitMessage.trim()) return;
    
    setLoading(true);
    try {
      const response = await fetch("/api/devops/git/commit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          node: selectedNode,
          message: commitMessage,
        }),
      });
      if (response.ok) {
        setCommitMessage("");
        await refreshGitStatus();
      }
    } catch (error) {
      console.error("Git commit failed:", error);
    } finally {
      setLoading(false);
    }
  };

  const stageFile = async (file: string) => {
    try {
      await fetch("/api/devops/git/stage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ node: selectedNode, files: [file] }),
      });
      await refreshGitStatus();
    } catch (error) {
      console.error("Failed to stage file:", error);
    }
  };

  const unstageFile = async (file: string) => {
    try {
      await fetch("/api/devops/git/unstage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ node: selectedNode, files: [file] }),
      });
      await refreshGitStatus();
    } catch (error) {
      console.error("Failed to unstage file:", error);
    }
  };

  useEffect(() => {
    refreshGitStatus();
    checkRemoteTunnel();
    const interval = setInterval(() => {
      refreshGitStatus();
      checkRemoteTunnel();
    }, 15000);
    return () => clearInterval(interval);
  }, [selectedNode]);

  const totalChanges = 
    status.modified.length + 
    status.added.length + 
    status.deleted.length + 
    status.untracked.length;

  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--chat-border)]">
        <div className="flex items-center gap-2">
          <GitBranch size={16} className="text-[var(--chat-accent)]" />
          <span className="text-sm font-semibold text-[var(--chat-text)]">Git</span>
        </div>
        <button
          onClick={refreshGitStatus}
          disabled={loading}
          className="p-1 rounded hover:bg-[var(--chat-hover)] transition-colors"
          title="Refresh git status"
        >
          <RefreshCw 
            size={14} 
            className={`text-[var(--chat-muted)] ${loading ? "animate-spin" : ""}`} 
          />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {/* Current Branch & Remote Tunnel */}
        <section>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <GitBranch size={14} className="text-[var(--chat-muted)]" />
              <span className="text-sm font-medium text-[var(--chat-text)]">{status.branch}</span>
            </div>
            {status.ahead > 0 && (
              <span className="px-2 py-0.5 text-xs bg-green-500/20 text-green-400 rounded">
                ↑{status.ahead}
              </span>
            )}
            {status.behind > 0 && (
              <span className="px-2 py-0.5 text-xs bg-blue-500/20 text-blue-400 rounded">
                ↓{status.behind}
              </span>
            )}
          </div>

          {/* GitHub Remote Tunnel */}
          <div className="p-2 bg-[var(--chat-input-bg)] border border-[var(--chat-border)] rounded">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Wifi size={14} className={remoteTunnel.connected ? "text-green-500" : "text-gray-500"} />
                <span className="text-xs font-medium text-[var(--chat-text)]">
                  GitHub Remote Tunnel
                </span>
              </div>
              <div className="flex items-center gap-1">
                {remoteTunnel.connected ? (
                  <CheckCircle size={14} className="text-green-500" />
                ) : (
                  <Circle size={14} className="text-gray-500" />
                )}
              </div>
            </div>
            {remoteTunnel.connected && remoteTunnel.url ? (
              <div className="flex items-center gap-2">
                <a
                  href={remoteTunnel.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-[var(--chat-accent)] hover:underline flex items-center gap-1"
                >
                  {remoteTunnel.url}
                  <ExternalLink size={12} />
                </a>
              </div>
            ) : (
              <button
                onClick={connectRemoteTunnel}
                disabled={loading}
                className="w-full px-2 py-1 text-xs bg-[var(--chat-accent)] text-white rounded hover:bg-[var(--chat-accent)]/80 transition-colors disabled:opacity-50"
              >
                Connect Remote Tunnel
              </button>
            )}
            {remoteTunnel.error && (
              <p className="text-xs text-red-400 mt-1">{remoteTunnel.error}</p>
            )}
          </div>

          {/* Pull/Push Buttons */}
          <div className="grid grid-cols-2 gap-2 mt-2">
            <button
              onClick={gitPull}
              disabled={loading}
              className="flex items-center justify-center gap-2 px-3 py-2 text-xs bg-[var(--chat-input-bg)] hover:bg-[var(--chat-hover)] border border-[var(--chat-border)] rounded transition-colors disabled:opacity-50"
            >
              <Download size={14} />
              Pull
            </button>
            <button
              onClick={gitPush}
              disabled={loading || status.ahead === 0}
              className="flex items-center justify-center gap-2 px-3 py-2 text-xs bg-[var(--chat-input-bg)] hover:bg-[var(--chat-hover)] border border-[var(--chat-border)] rounded transition-colors disabled:opacity-50"
            >
              <Upload size={14} />
              Push
            </button>
          </div>
        </section>

        {/* Changes Summary */}
        <section>
          <h3 className="text-xs font-semibold text-[var(--chat-muted)] uppercase mb-2">
            Changes ({totalChanges})
          </h3>
          
          {totalChanges === 0 ? (
            <div className="text-xs text-[var(--chat-muted)] text-center py-4">
              No changes
            </div>
          ) : (
            <div className="space-y-1 max-h-60 overflow-y-auto">
              {/* Modified Files */}
              {status.modified.map((file) => (
                <div
                  key={file}
                  className="flex items-center justify-between px-2 py-1.5 bg-[var(--chat-input-bg)] border border-[var(--chat-border)] rounded text-xs hover:border-[var(--chat-accent)] transition-colors"
                >
                  <div className="flex items-center gap-2 flex-1">
                    <FileText size={12} className="text-yellow-500" />
                    <span className="text-[var(--chat-text)] truncate">{file}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => stageFile(file)}
                      className="p-1 rounded hover:bg-[var(--chat-hover)] transition-colors"
                      title="Stage file"
                    >
                      <Plus size={12} className="text-green-500" />
                    </button>
                  </div>
                </div>
              ))}
              
              {/* Added Files */}
              {status.added.map((file) => (
                <div
                  key={file}
                  className="flex items-center justify-between px-2 py-1.5 bg-[var(--chat-input-bg)] border border-green-500/30 rounded text-xs"
                >
                  <div className="flex items-center gap-2 flex-1">
                    <Plus size={12} className="text-green-500" />
                    <span className="text-[var(--chat-text)] truncate">{file}</span>
                  </div>
                  <button
                    onClick={() => unstageFile(file)}
                    className="p-1 rounded hover:bg-[var(--chat-hover)] transition-colors"
                    title="Unstage file"
                  >
                    <Minus size={12} className="text-red-500" />
                  </button>
                </div>
              ))}
              
              {/* Deleted Files */}
              {status.deleted.map((file) => (
                <div
                  key={file}
                  className="flex items-center justify-between px-2 py-1.5 bg-[var(--chat-input-bg)] border border-red-500/30 rounded text-xs"
                >
                  <div className="flex items-center gap-2 flex-1">
                    <Minus size={12} className="text-red-500" />
                    <span className="text-[var(--chat-text)] truncate line-through">{file}</span>
                  </div>
                </div>
              ))}
              
              {/* Untracked Files */}
              {status.untracked.map((file) => (
                <div
                  key={file}
                  className="flex items-center justify-between px-2 py-1.5 bg-[var(--chat-input-bg)] border border-[var(--chat-border)] rounded text-xs hover:border-[var(--chat-accent)] transition-colors"
                >
                  <div className="flex items-center gap-2 flex-1">
                    <Circle size={12} className="text-gray-500" />
                    <span className="text-[var(--chat-muted)] truncate">{file}</span>
                  </div>
                  <button
                    onClick={() => stageFile(file)}
                    className="p-1 rounded hover:bg-[var(--chat-hover)] transition-colors"
                    title="Stage file"
                  >
                    <Plus size={12} className="text-green-500" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Commit Section */}
        {status.added.length > 0 && (
          <section>
            <h3 className="text-xs font-semibold text-[var(--chat-muted)] uppercase mb-2 flex items-center gap-2">
              <GitCommit size={12} />
              Commit
            </h3>
            <div className="space-y-2">
              <textarea
                value={commitMessage}
                onChange={(e) => setCommitMessage(e.target.value)}
                placeholder="Commit message..."
                className="w-full px-3 py-2 text-xs bg-[var(--chat-input-bg)] text-[var(--chat-text)] border border-[var(--chat-border)] rounded resize-none focus:outline-none focus:border-[var(--chat-accent)] transition-colors"
                rows={3}
              />
              <button
                onClick={gitCommit}
                disabled={loading || !commitMessage.trim()}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs bg-[var(--chat-accent)] text-white rounded hover:bg-[var(--chat-accent)]/80 transition-colors disabled:opacity-50"
              >
                <GitCommit size={14} />
                Commit Changes
              </button>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
