"use client";

import { useState, useCallback, useEffect } from "react";
import { desktop } from "@/lib/desktop";
import { MarkdownRenderer } from "@/components/shared/markdown-renderer";
import Editor from "@monaco-editor/react";
import { Play, Plus, Trash2, ChevronUp, ChevronDown, Code2, FileText } from "lucide-react";

// ---------------------------------------------------------------------------
// nbformat types (subset)
// ---------------------------------------------------------------------------
type CellType = "code" | "markdown" | "raw";

interface OutputItem {
  output_type: "stream" | "display_data" | "execute_result" | "error";
  text?:       string | string[];
  data?:       Record<string, string | string[]>;
  ename?:      string;
  evalue?:     string;
  traceback?:  string[];
}

interface Cell {
  id:           string;
  cell_type:    CellType;
  source:       string[];
  outputs?:     OutputItem[];
  execution_count?: number | null;
  metadata?:    Record<string, unknown>;
}

interface Notebook {
  nbformat:       number;
  nbformat_minor: number;
  metadata:       Record<string, unknown>;
  cells:          Cell[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function src(lines: string[]): string {
  return lines.join("");
}

function genId(): string {
  return Math.random().toString(36).slice(2, 10);
}

function parseNotebook(json: string): Notebook {
  const nb = JSON.parse(json) as Notebook;
  // Ensure cells have ids (nbformat 4.5+)
  nb.cells = (nb.cells ?? []).map((c) => ({ ...c, id: c.id ?? genId() }));
  return nb;
}

function serializeNotebook(nb: Notebook): string {
  return JSON.stringify(nb, null, 1);
}

// ---------------------------------------------------------------------------
// Output rendering
// ---------------------------------------------------------------------------
function CellOutput({ output }: { output: OutputItem }) {
  if (output.output_type === "stream") {
    const text = Array.isArray(output.text) ? output.text.join("") : (output.text ?? "");
    return (
      <pre className="text-[11px] font-mono whitespace-pre-wrap text-[var(--chat-text)] leading-relaxed">
        {text}
      </pre>
    );
  }

  if (output.output_type === "error") {
    return (
      <div className="text-[11px] font-mono">
        <div className="text-red-400 font-semibold">{output.ename}: {output.evalue}</div>
        {output.traceback?.map((line, i) => (
          <div key={i} className="text-red-300/70 whitespace-pre-wrap"
               dangerouslySetInnerHTML={{ __html: line.replace(/\x1b\[[0-9;]*m/g, "") }} />
        ))}
      </div>
    );
  }

  const data = output.data ?? {};

  // Image
  const imgData = data["image/png"] ?? data["image/jpeg"] ?? data["image/svg+xml"];
  if (imgData) {
    const mime = data["image/png"] ? "image/png"
               : data["image/jpeg"] ? "image/jpeg"
               : "image/svg+xml";
    const b64  = Array.isArray(imgData) ? imgData.join("") : imgData;
    return (
      <img
        src={`data:${mime};base64,${b64}`}
        alt="cell output"
        className="max-w-full rounded"
      />
    );
  }

  // HTML
  const html = data["text/html"];
  if (html) {
    const raw = Array.isArray(html) ? html.join("") : html;
    return (
      <div
        className="text-[12px] text-[var(--chat-text)] overflow-x-auto"
        dangerouslySetInnerHTML={{ __html: raw }}
      />
    );
  }

  // Plain text
  const text = data["text/plain"];
  if (text) {
    const raw = Array.isArray(text) ? text.join("") : text;
    return <pre className="text-[11px] font-mono whitespace-pre-wrap text-[var(--chat-text)]">{raw}</pre>;
  }

  return null;
}

// ---------------------------------------------------------------------------
// Single cell
// ---------------------------------------------------------------------------
interface CellProps {
  cell:     Cell;
  index:    number;
  total:    number;
  selected: boolean;
  onSelect: () => void;
  onChange: (source: string) => void;
  onRun:    () => void;
  onDelete: () => void;
  onMove:   (dir: "up" | "down") => void;
  onAdd:    (type: CellType) => void;
}

function NotebookCell({ cell, index, total, selected, onSelect, onChange, onRun, onDelete, onMove, onAdd }: CellProps) {
  const [showAdd, setShowAdd] = useState(false);
  const source = src(cell.source);

  return (
    <div
      className={`group relative border rounded-lg overflow-hidden transition-colors ${
        selected
          ? "border-[var(--chat-accent)]/50 shadow-sm"
          : "border-[var(--chat-border)] hover:border-[var(--chat-border)]/80"
      }`}
      onClick={onSelect}
    >
      {/* Cell header */}
      <div className="flex items-center gap-1.5 px-3 py-1 bg-[var(--chat-surface)] border-b border-[var(--chat-border)]">
        <span className="text-[10px] text-[var(--chat-muted)] font-mono min-w-[2rem]">
          {cell.cell_type === "code" ? `[${cell.execution_count ?? " "}]` : cell.cell_type}
        </span>
        <div className="flex-1" />

        {selected && (
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <button onClick={(e) => { e.stopPropagation(); onMove("up"); }} disabled={index === 0}
              className="p-0.5 text-[var(--chat-muted)] hover:text-[var(--chat-text)] disabled:opacity-30">
              <ChevronUp size={12} />
            </button>
            <button onClick={(e) => { e.stopPropagation(); onMove("down"); }} disabled={index === total - 1}
              className="p-0.5 text-[var(--chat-muted)] hover:text-[var(--chat-text)] disabled:opacity-30">
              <ChevronDown size={12} />
            </button>
            {cell.cell_type === "code" && (
              <button onClick={(e) => { e.stopPropagation(); onRun(); }}
                className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-[var(--chat-accent)] text-canvas hover:opacity-80">
                <Play size={10} /> Run
              </button>
            )}
            <button onClick={(e) => { e.stopPropagation(); onDelete(); }}
              className="p-0.5 text-[var(--chat-muted)] hover:text-red-400">
              <Trash2 size={12} />
            </button>
          </div>
        )}
      </div>

      {/* Cell body */}
      <div className="bg-[var(--chat-bg)]">
        {cell.cell_type === "markdown" ? (
          selected ? (
            <textarea
              className="w-full min-h-[80px] p-3 bg-transparent font-mono text-[12px] text-[var(--chat-text)] resize-y focus:outline-none"
              value={source}
              onChange={(e) => onChange(e.target.value)}
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <div className="px-4 py-2 text-sm prose prose-invert max-w-none">
              <MarkdownRenderer content={source || "*Empty markdown cell*"} />
            </div>
          )
        ) : (
          <Editor
            height={Math.max(60, source.split("\n").length * 19 + 8)}
            language="python"
            value={source}
            onChange={(v) => onChange(v ?? "")}
            options={{
              minimap: { enabled: false },
              lineNumbers: "on",
              scrollBeyondLastLine: false,
              fontSize: 12,
              lineHeight: 19,
              padding: { top: 4, bottom: 4 },
              folding: false,
              overviewRulerLanes: 0,
              scrollbar: { vertical: "hidden", horizontal: "hidden" },
              renderLineHighlight: "none",
              fontFamily: "'Cascadia Code', 'Fira Code', Consolas, monospace",
            }}
            theme="vs-dark"
          />
        )}
      </div>

      {/* Outputs */}
      {cell.cell_type === "code" && cell.outputs && cell.outputs.length > 0 && (
        <div className="border-t border-[var(--chat-border)] px-4 py-2 space-y-1 bg-[var(--chat-bg)]/50">
          {cell.outputs.map((out, i) => <CellOutput key={i} output={out} />)}
        </div>
      )}

      {/* Add cell below (on hover) */}
      {selected && (
        <div className="border-t border-[var(--chat-border)] flex items-center justify-center gap-2 py-1 bg-[var(--chat-surface)]"
             onMouseEnter={() => setShowAdd(true)} onMouseLeave={() => setShowAdd(false)}>
          <button onClick={(e) => { e.stopPropagation(); onAdd("code"); }}
            className="flex items-center gap-1 text-[10px] text-[var(--chat-muted)] hover:text-[var(--chat-text)] px-2 py-0.5 rounded hover:bg-[var(--chat-surface2)]">
            <Code2 size={10} /> + Code
          </button>
          <button onClick={(e) => { e.stopPropagation(); onAdd("markdown"); }}
            className="flex items-center gap-1 text-[10px] text-[var(--chat-muted)] hover:text-[var(--chat-text)] px-2 py-0.5 rounded hover:bg-[var(--chat-surface2)]">
            <FileText size={10} /> + Markdown
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Notebook viewer / editor
// ---------------------------------------------------------------------------
interface Props {
  path:    string;
  onClose: () => void;
}

export function NotebookViewer({ path, onClose }: Props) {
  const [nb, setNb]           = useState<Notebook | null>(null);
  const [error, setError]     = useState<string>("");
  const [selected, setSelected] = useState<string | null>(null);
  const [dirty, setDirty]     = useState(false);
  const [saving, setSaving]   = useState(false);

  const filename = path.split(/[/\\]/).pop() ?? path;

  // Load
  useEffect(() => {
    const bridge = desktop();
    if (!bridge) { setError("Notebook editing requires the Memex Desktop app."); return; }
    bridge.fs.readFile(path)
      .then((text) => {
        const parsed = parseNotebook(text);
        setNb(parsed);
        setSelected(parsed.cells[0]?.id ?? null);
      })
      .catch((e) => setError(String(e)));
  }, [path]);

  const update = useCallback((fn: (nb: Notebook) => Notebook) => {
    setNb((prev) => { if (!prev) return prev; const next = fn(prev); setDirty(true); return next; });
  }, []);

  const save = async () => {
    if (!nb) return;
    const bridge = desktop();
    if (!bridge) return;
    setSaving(true);
    try {
      await bridge.fs.writeFile(path, serializeNotebook(nb));
      setDirty(false);
    } catch {}
    setSaving(false);
  };

  const changeCell = (id: string, source: string) =>
    update((nb) => ({
      ...nb,
      cells: nb.cells.map((c) => c.id === id ? { ...c, source: [source] } : c),
    }));

  const deleteCell = (id: string) =>
    update((nb) => ({ ...nb, cells: nb.cells.filter((c) => c.id !== id) }));

  const moveCell = (id: string, dir: "up" | "down") =>
    update((nb) => {
      const idx = nb.cells.findIndex((c) => c.id === id);
      if (idx === -1) return nb;
      const cells = [...nb.cells];
      const swap = dir === "up" ? idx - 1 : idx + 1;
      if (swap < 0 || swap >= cells.length) return nb;
      [cells[idx], cells[swap]] = [cells[swap], cells[idx]];
      return { ...nb, cells };
    });

  const addCell = (afterId: string, type: CellType) => {
    const newCell: Cell = { id: genId(), cell_type: type, source: [""], outputs: [], execution_count: null };
    update((nb) => {
      const idx = nb.cells.findIndex((c) => c.id === afterId);
      const cells = [...nb.cells];
      cells.splice(idx + 1, 0, newCell);
      return { ...nb, cells };
    });
    setSelected(newCell.id);
  };

  // Run cell via Jupyter kernel (if available via bridge)
  const runCell = async (id: string) => {
    const cell = nb?.cells.find((c) => c.id === id);
    if (!cell) return;
    const code = src(cell.source);
    // Relay to agent_runtime for execution (future: real kernel)
    const bridge = desktop();
    if (bridge) {
      bridge.shell.exec(`python -c ${JSON.stringify(code)}`).then(({ stdout, stderr }) => {
        const outputs: OutputItem[] = [];
        if (stdout) outputs.push({ output_type: "stream", text: [stdout] });
        if (stderr) outputs.push({ output_type: "stream", text: [stderr] });
        update((nb) => ({
          ...nb,
          cells: nb.cells.map((c) => c.id === id
            ? { ...c, outputs, execution_count: (c.execution_count ?? 0) + 1 }
            : c),
        }));
      });
    }
  };

  if (error) return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)]">
      <div className="px-4 py-3 text-red-400 text-sm">{error}</div>
    </div>
  );

  if (!nb) return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)] items-center justify-center">
      <div className="text-[var(--chat-muted)] text-sm animate-pulse">Loading notebook…</div>
    </div>
  );

  const kernelName = (nb.metadata?.kernelspec as Record<string, string>)?.display_name ?? "Python";

  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)]">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-[var(--chat-border)] bg-[var(--chat-surface)] flex-shrink-0">
        <span className="text-xs font-mono text-[var(--chat-text)] font-medium">{filename}</span>
        {dirty && <span className="w-1.5 h-1.5 rounded-full bg-[var(--chat-accent)]" title="Unsaved" />}
        <span className="text-[10px] text-[var(--chat-muted)] px-1.5 py-0.5 rounded border border-[var(--chat-border)]">
          {kernelName}
        </span>
        <div className="flex-1" />
        <button
          onClick={() => {
            const id = genId();
            const c: Cell = { id, cell_type: "code", source: [""], outputs: [], execution_count: null };
            update((nb) => ({ ...nb, cells: [...nb.cells, c] }));
            setSelected(id);
          }}
          className="flex items-center gap-1 text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)] px-2 py-1 rounded border border-[var(--chat-border)] hover:border-[var(--chat-accent)]/40"
        >
          <Plus size={12} /> Cell
        </button>
        {dirty && (
          <button onClick={save} disabled={saving}
            className="px-2.5 py-1 text-xs bg-[var(--chat-accent)] text-canvas rounded hover:opacity-80 disabled:opacity-50">
            {saving ? "Saving…" : "Save"}
          </button>
        )}
        <button onClick={onClose} className="text-[var(--chat-muted)] hover:text-[var(--chat-text)] text-lg leading-none">×</button>
      </div>

      {/* Cells */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {nb.cells.map((cell, i) => (
          <NotebookCell
            key={cell.id}
            cell={cell}
            index={i}
            total={nb.cells.length}
            selected={selected === cell.id}
            onSelect={() => setSelected(cell.id)}
            onChange={(src) => changeCell(cell.id, src)}
            onRun={() => runCell(cell.id)}
            onDelete={() => deleteCell(cell.id)}
            onMove={(dir) => moveCell(cell.id, dir)}
            onAdd={(type) => addCell(cell.id, type)}
          />
        ))}

        {nb.cells.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-[var(--chat-muted)] gap-3">
            <p className="text-sm">Empty notebook</p>
            <button
              onClick={() => {
                const id = genId();
                update((nb) => ({ ...nb, cells: [{ id, cell_type: "code", source: [""], outputs: [], execution_count: null }] }));
                setSelected(id);
              }}
              className="text-xs px-3 py-1.5 rounded border border-[var(--chat-border)] hover:border-[var(--chat-accent)]/40 hover:text-[var(--chat-text)]"
            >
              + Add first cell
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
