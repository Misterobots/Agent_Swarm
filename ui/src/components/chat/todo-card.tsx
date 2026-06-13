"use client";

import type { TodoItem } from "@/types/chat";

const STATUS_GLYPH: Record<TodoItem["status"], string> = {
  completed: "✓",
  in_progress: "▸",
  pending: "○",
};

/**
 * Renders the agent's TodoWrite task list (Claude-Code-style plan card).
 * The backend sends the full list on each update, so this is a pure render.
 */
export function TodoCard({ todos }: { todos: TodoItem[] }) {
  if (!todos?.length) return null;
  const done = todos.filter((t) => t.status === "completed").length;

  return (
    <div
      className="mt-3 rounded-lg overflow-hidden"
      style={{ border: "1px solid var(--chat-border)", background: "var(--chat-surface)" }}
    >
      <div
        className="px-3 py-1.5 text-xs font-medium flex items-center justify-between"
        style={{ color: "var(--chat-muted)", borderBottom: "1px solid var(--chat-border)" }}
      >
        <span>Plan</span>
        <span>
          {done}/{todos.length}
        </span>
      </div>
      <ul className="px-3 py-2 space-y-1 m-0 list-none">
        {todos.map((t, i) => {
          const isDone = t.status === "completed";
          const isActive = t.status === "in_progress";
          const label = isActive && t.activeForm ? t.activeForm : t.content;
          return (
            <li key={i} className="flex items-start gap-2 text-sm">
              <span
                style={{
                  color: isDone || isActive ? "var(--chat-accent-strong)" : "var(--chat-muted)",
                  marginTop: "1px",
                }}
              >
                {STATUS_GLYPH[t.status]}
              </span>
              <span
                style={{
                  textDecoration: isDone ? "line-through" : "none",
                  opacity: isDone ? 0.65 : 1,
                  fontWeight: isActive ? 600 : 400,
                  color: isDone ? "var(--chat-muted)" : "inherit",
                }}
              >
                {label}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
