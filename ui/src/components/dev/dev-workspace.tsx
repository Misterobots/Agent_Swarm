"use client";

import { Panel, Group, Separator } from "react-resizable-panels";
import { ChatView } from "@/components/chat/chat-view";
import { FileCode2, Terminal } from "lucide-react";

function EditorPlaceholder() {
  return (
    <div className="flex flex-col h-full bg-[#0e1117]">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-zinc-800 text-xs text-zinc-500">
        <FileCode2 size={13} />
        <span>Editor</span>
      </div>
      <div className="flex-1 flex items-center justify-center text-zinc-600">
        <div className="text-center">
          <FileCode2 size={40} className="mx-auto mb-3 text-zinc-700" />
          <p className="text-sm font-medium text-zinc-500">Editor Pane</p>
          <p className="text-xs text-zinc-600 mt-1">Monaco integration — coming soon</p>
        </div>
      </div>
    </div>
  );
}

function TerminalPlaceholder() {
  return (
    <div className="flex flex-col h-full bg-[#0a0a14]">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-zinc-800 text-xs text-zinc-500">
        <Terminal size={13} />
        <span>Terminal</span>
      </div>
      <div className="flex-1 flex items-center justify-center text-zinc-600">
        <div className="text-center">
          <Terminal size={32} className="mx-auto mb-2 text-zinc-700" />
          <p className="text-xs text-zinc-600">xterm.js integration — coming soon</p>
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

      <Separator className="w-1 bg-zinc-800 hover:bg-cyan-600 transition-colors" />

      {/* Right side: editor + terminal stacked */}
      <Panel defaultSize="65%" minSize="30%">
        <Group orientation="vertical">
          {/* Editor pane */}
          <Panel defaultSize="65%" minSize="20%">
            <EditorPlaceholder />
          </Panel>

          <Separator className="h-1 bg-zinc-800 hover:bg-cyan-600 transition-colors" />

          {/* Terminal pane */}
          <Panel defaultSize="35%" minSize="15%">
            <TerminalPlaceholder />
          </Panel>
        </Group>
      </Panel>
    </Group>
  );
}
