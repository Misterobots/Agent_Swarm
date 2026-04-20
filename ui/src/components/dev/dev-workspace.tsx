"use client";

import { Panel, Group, Separator } from "react-resizable-panels";
import { ChatView } from "@/components/chat/chat-view";
import { EditorPane } from "./editor-pane";
import { TerminalPane } from "./terminal-pane";
import { useIsMobile } from "@/lib/hooks/use-mobile";

export function DevWorkspace() {
  const { isMobile } = useIsMobile();

  // On mobile, show only the chat pane (editor+terminal are impractical)
  if (isMobile) {
    return <ChatView showDevContext />;
  }

  return (
    <Group orientation="horizontal" className="h-full">
      {/* Chat pane */}
      <Panel defaultSize="35%" minSize="25%">
        <ChatView showDevContext />
      </Panel>

      <Separator className="w-1 bg-[var(--chat-border)] hover:bg-[var(--chat-accent)] transition-colors" />

      {/* Right side: editor + terminal stacked */}
      <Panel defaultSize="65%" minSize="30%">
        <Group orientation="vertical">
          {/* Editor pane */}
          <Panel defaultSize="65%" minSize="20%">
            <EditorPane />
          </Panel>

          <Separator className="h-1 bg-[var(--chat-border)] hover:bg-[var(--chat-accent)] transition-colors" />

          {/* Terminal pane */}
          <Panel defaultSize="35%" minSize="15%">
            <TerminalPane />
          </Panel>
        </Group>
      </Panel>
    </Group>
  );
}
