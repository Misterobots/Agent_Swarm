"use client";

import { useState, useEffect, useRef } from "react";
import { 
  FileText, 
  Search, 
  Filter, 
  Download, 
  Trash2, 
  Pause, 
  Play,
  AlertCircle,
  Info,
  AlertTriangle,
  X
} from "lucide-react";

interface LogEntry {
  timestamp: string;
  level: "INFO" | "WARN" | "ERROR" | "DEBUG";
  source: string;
  message: string;
}

interface LogSource {
  id: string;
  name: string;
  node: string;
  active: boolean;
}

const LOG_SOURCES: LogSource[] = [
  { id: "agent_runtime", name: "Agent Runtime", node: "Turing", active: false },
  { id: "memex_ui", name: "Memex UI", node: "Turing", active: false },
  { id: "postgres", name: "PostgreSQL", node: "Hopper", active: false },
  { id: "redis", name: "Redis", node: "Hopper", active: false },
  { id: "langfuse", name: "Langfuse", node: "Hopper", active: false },
  { id: "ollama", name: "Ollama", node: "Turing", active: false },
];

export function LogViewer() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [sources, setSources] = useState<LogSource[]>(LOG_SOURCES);
  const [searchQuery, setSearchQuery] = useState("");
  const [levelFilter, setLevelFilter] = useState<string>("all");
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [isPaused, setIsPaused] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [showFilters, setShowFilters] = useState(false);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const logsContainerRef = useRef<HTMLDivElement>(null);

  const getLevelIcon = (level: string) => {
    switch (level) {
      case "ERROR":
        return <AlertCircle className="text-red-500" size={14} />;
      case "WARN":
        return <AlertTriangle className="text-yellow-500" size={14} />;
      case "INFO":
        return <Info className="text-blue-500" size={14} />;
      default:
        return <FileText className="text-gray-500" size={14} />;
    }
  };

  const getLevelColor = (level: string) => {
    switch (level) {
      case "ERROR":
        return "text-red-400";
      case "WARN":
        return "text-yellow-400";
      case "INFO":
        return "text-blue-400";
      default:
        return "text-gray-400";
    }
  };

  const toggleSource = (sourceId: string) => {
    setSources((prev) =>
      prev.map((s) => 
        s.id === sourceId ? { ...s, active: !s.active } : s
      )
    );
  };

  const streamLogs = async (sourceId: string) => {
    try {
      const response = await fetch(`/api/devops/logs/stream?source=${sourceId}`);
      if (!response.ok) return;

      const reader = response.body?.getReader();
      if (!reader) return;

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const entry: LogEntry = JSON.parse(line);
            if (!isPaused) {
              setLogs((prev) => [...prev.slice(-999), entry]); // Keep last 1000 logs
            }
          } catch (e) {
            // Plain text log line
            const entry: LogEntry = {
              timestamp: new Date().toISOString(),
              level: "INFO",
              source: sourceId,
              message: line,
            };
            if (!isPaused) {
              setLogs((prev) => [...prev.slice(-999), entry]);
            }
          }
        }
      }
    } catch (error) {
      console.error(`Failed to stream logs from ${sourceId}:`, error);
    }
  };

  const fetchLogs = async () => {
    const activeSources = sources.filter((s) => s.active);
    if (activeSources.length === 0) return;

    try {
      const sourceIds = activeSources.map((s) => s.id).join(",");
      const response = await fetch(`/api/devops/logs?sources=${sourceIds}&limit=100`);
      if (response.ok) {
        const data = await response.json();
        setLogs(data.logs || []);
      }
    } catch (error) {
      console.error("Failed to fetch logs:", error);
    }
  };

  const clearLogs = () => {
    setLogs([]);
  };

  const downloadLogs = () => {
    const logText = filteredLogs
      .map((log) => `[${log.timestamp}] [${log.level}] [${log.source}] ${log.message}`)
      .join("\n");
    
    const blob = new Blob([logText], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `logs-${new Date().toISOString()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const filteredLogs = logs.filter((log) => {
    if (searchQuery && !log.message.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    if (levelFilter !== "all" && log.level !== levelFilter) {
      return false;
    }
    if (sourceFilter !== "all" && log.source !== sourceFilter) {
      return false;
    }
    return true;
  });

  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [filteredLogs, autoScroll]);

  useEffect(() => {
    // Start streaming for active sources
    const activeSources = sources.filter((s) => s.active);
    activeSources.forEach((source) => {
      streamLogs(source.id);
    });
  }, [sources.map((s) => s.active).join(",")]);

  const activeSources = sources.filter((s) => s.active);

  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--chat-border)]">
        <div className="flex items-center gap-2">
          <FileText size={16} className="text-[var(--chat-accent)]" />
          <span className="text-sm font-semibold text-[var(--chat-text)]">Logs</span>
          {activeSources.length > 0 && (
            <span className="px-2 py-0.5 text-xs bg-[var(--chat-accent)]/20 text-[var(--chat-accent)] rounded">
              {activeSources.length} active
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`p-1.5 rounded transition-colors ${
              showFilters ? "bg-[var(--chat-accent)] text-white" : "hover:bg-[var(--chat-hover)]"
            }`}
            title="Toggle filters"
          >
            <Filter size={14} />
          </button>
          <button
            onClick={() => setIsPaused(!isPaused)}
            className="p-1.5 rounded hover:bg-[var(--chat-hover)] transition-colors"
            title={isPaused ? "Resume" : "Pause"}
          >
            {isPaused ? <Play size={14} /> : <Pause size={14} />}
          </button>
          <button
            onClick={downloadLogs}
            className="p-1.5 rounded hover:bg-[var(--chat-hover)] transition-colors"
            title="Download logs"
          >
            <Download size={14} />
          </button>
          <button
            onClick={clearLogs}
            className="p-1.5 rounded hover:bg-[var(--chat-hover)] transition-colors text-red-400"
            title="Clear logs"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="px-3 py-2 border-b border-[var(--chat-border)] space-y-2">
          {/* Search */}
          <div className="relative">
            <Search size={14} className="absolute left-2 top-2 text-[var(--chat-muted)]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search logs..."
              className="w-full pl-8 pr-3 py-1.5 text-xs bg-[var(--chat-input-bg)] text-[var(--chat-text)] border border-[var(--chat-border)] rounded focus:outline-none focus:border-[var(--chat-accent)] transition-colors"
            />
          </div>

          {/* Level and Source Filters */}
          <div className="grid grid-cols-2 gap-2">
            <select
              value={levelFilter}
              onChange={(e) => setLevelFilter(e.target.value)}
              className="px-2 py-1.5 text-xs bg-[var(--chat-input-bg)] text-[var(--chat-text)] border border-[var(--chat-border)] rounded focus:outline-none focus:border-[var(--chat-accent)]"
            >
              <option value="all">All Levels</option>
              <option value="ERROR">Error</option>
              <option value="WARN">Warning</option>
              <option value="INFO">Info</option>
              <option value="DEBUG">Debug</option>
            </select>
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              className="px-2 py-1.5 text-xs bg-[var(--chat-input-bg)] text-[var(--chat-text)] border border-[var(--chat-border)] rounded focus:outline-none focus:border-[var(--chat-accent)]"
            >
              <option value="all">All Sources</option>
              {sources.map((source) => (
                <option key={source.id} value={source.id}>
                  {source.name}
                </option>
              ))}
            </select>
          </div>

          {/* Log Sources */}
          <div className="flex flex-wrap gap-1">
            {sources.map((source) => (
              <button
                key={source.id}
                onClick={() => toggleSource(source.id)}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  source.active
                    ? "bg-[var(--chat-accent)] text-white"
                    : "bg-[var(--chat-input-bg)] text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
                }`}
              >
                {source.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Logs Display */}
      <div 
        ref={logsContainerRef}
        className="flex-1 overflow-y-auto px-3 py-2 font-mono text-xs space-y-1"
        onScroll={(e) => {
          const element = e.currentTarget;
          const isAtBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 50;
          setAutoScroll(isAtBottom);
        }}
      >
        {filteredLogs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[var(--chat-muted)]">
            <FileText size={32} className="mb-2 opacity-50" />
            <p className="text-sm">No logs to display</p>
            {activeSources.length === 0 && (
              <p className="text-xs mt-1">Select a log source above</p>
            )}
          </div>
        ) : (
          filteredLogs.map((log, index) => (
            <div
              key={index}
              className="flex items-start gap-2 px-2 py-1 hover:bg-[var(--chat-hover)] rounded group"
            >
              {getLevelIcon(log.level)}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-[var(--chat-muted)]">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                  <span className={`font-semibold ${getLevelColor(log.level)}`}>
                    {log.level}
                  </span>
                  <span className="px-1.5 py-0.5 bg-[var(--chat-input-bg)] text-[var(--chat-muted)] rounded text-xs">
                    {log.source}
                  </span>
                </div>
                <div className="text-[var(--chat-text)] whitespace-pre-wrap break-words">
                  {log.message}
                </div>
              </div>
            </div>
          ))
        )}
        <div ref={logsEndRef} />
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-3 py-1.5 border-t border-[var(--chat-border)] text-xs text-[var(--chat-muted)]">
        <span>{filteredLogs.length} logs</span>
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
            className="w-3 h-3"
          />
          Auto-scroll
        </label>
      </div>
    </div>
  );
}
