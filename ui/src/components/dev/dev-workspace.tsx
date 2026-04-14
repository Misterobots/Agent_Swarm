"use client";

import { Panel, Group, Separator } from "react-resizable-panels";
import { ChatView } from "@/components/chat/chat-view";
import { FileCode2, Terminal } from "lucide-react";

function EditorPlaceholder() {
  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)]">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-[var(--chat-border)] text-xs text-[var(--chat-muted)]">
        <FileCode2 size={13} />
        <span>Editor</span>
      </div>
      <div className="flex-1 flex items-center justify-center text-[var(--chat-muted)]">
        <div className="text-center">
          <FileCode2 size={40} className="mx-auto mb-3 text-[var(--chat-muted)]" />
          <p className="text-sm font-medium text-[var(--chat-muted)]">Editor Pane</p>
          <p className="text-xs text-[var(--chat-muted)] mt-1">Monaco integration — coming soon</p>
        </div>
      </div>
    </div>
  );
}

function TerminalPlaceholder() {
  return (
    <div className="flex flex-col h-full bg-[var(--chat-bg)]">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-[var(--chat-border)] text-xs text-[var(--chat-muted)]">
        <Terminal size={13} />
        <span>Terminal</span>
      </div>
      <div className="flex-1 flex items-center justify-center text-[var(--chat-muted)]">
        <div className="text-center">
          <Terminal size={32} className="mx-auto mb-2 text-[var(--chat-muted)]" />
          <p className="text-xs text-[var(--chat-muted)]">xterm.js integration — coming soon</p>
        </div>
      </div>
    </div>
  );
}

export function DevWorkspace() {
  return (
    <Group orientation="horizontal" className="h-full">
      {/* Chat pane */}
      <Panel defaultSize="35%" minSize="25%">
        <ChatView />
      </Panel>

      <Separator className="w-1 bg-[var(--chat-border)] hover:bg-[var(--chat-accent)] transition-colors" />

      {/* Right side: editor + terminal stacked */}
      <Panel defaultSize="65%" minSize="30%">
        <Group orientation="vertical">
          {/* Editor pane */}
          <Panel defaultSize="65%" minSize="20%">
            <EditorPlaceholder />
          </Panel>

          <Separator className="h-1 bg-[var(--chat-border)] hover:bg-[var(--chat-accent)] transition-colors" />

          {/* Terminal pane */}
          <Panel defaultSize="35%" minSize="15%">
            <TerminalPlaceholder />
          </Panel>
        </Group>
      </Panel>
    </Group>
  );
}
