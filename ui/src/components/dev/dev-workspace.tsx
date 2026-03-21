"use client";

import dynamic from "next/dynamic";
import { Panel, Group, Separator } from "react-resizable-panels";
import { ChatView } from "@/components/chat/chat-view";

// Dynamic imports — Monaco and xterm require browser APIs
const EditorPane = dynamic(
  () => import("./editor-pane").then((m) => ({ default: m.EditorPane })),
  { ssr: false }
);

const TerminalPane = dynamic(
  () => import("./terminal-pane").then((m) => ({ default: m.TerminalPane })),
  { ssr: false }
);

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
            <EditorPane />
          </Panel>

          <Separator className="h-1 bg-zinc-800 hover:bg-cyan-600 transition-colors" />

          {/* Terminal pane */}
          <Panel defaultSize="35%" minSize="15%">
            <TerminalPane />
          </Panel>
        </Group>
      </Panel>
    </Group>
  );
}
