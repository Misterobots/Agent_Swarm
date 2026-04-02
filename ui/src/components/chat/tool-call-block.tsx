"use client";

import type { ToolCallEvent } from "@/types/chat";

interface ToolCallBlockProps {
  toolCalls: ToolCallEvent[];
}

export function ToolCallBlock({ toolCalls }: ToolCallBlockProps) {
  if (!toolCalls.length) return null;

  return (
    <div className="mt-3 rounded-md border border-[#3b332e] bg-[#11100f] overflow-hidden">
      <div className="px-3 py-2 border-b border-[#2a2521] text-xs uppercase tracking-wider text-[#cc9a84]">
        Tool Calls ({toolCalls.length})
      </div>
      <div className="divide-y divide-[#2a2521]">
        {toolCalls.map((t, idx) => (
          <div key={`${t.tool_call_id || t.timestamp}-${idx}`} className="px-3 py-2">
            <p className="text-xs text-[#d9b8a7]">
              {new Date(t.timestamp).toLocaleTimeString()} | {t.tool_name}
            </p>
            {t.content ? <p className="text-xs text-zinc-300 mt-1">{t.content}</p> : null}
            {t.tool_input ? (
              <pre className="mt-2 text-xs text-zinc-400 overflow-x-auto whitespace-pre-wrap">
                {JSON.stringify(t.tool_input, null, 2)}
              </pre>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
