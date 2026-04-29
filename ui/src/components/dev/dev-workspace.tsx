"use client";

import { Panel, Group, Separator } from "react-resizable-panels";
import { ChatView } from "@/components/chat/chat-view";
import { EditorPane } from "./editor-pane";
import { TabbedTerminal } from "./tabbed-terminal";
import { FileTree } from "./file-tree";
import { OutputPreview } from "./output-preview";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useIsMobile } from "@/lib/hooks/use-mobile";
import { useDevStore } from "@/lib/stores/dev-store";

export function DevWorkspace() {
  const { isMobile } = useIsMobile();
  const router = useRouter();
  const { showFileTree, showOutputPreview } = useDevStore();

  // Redirect to chat on mobile — Dev workspace is desktop-only
  useEffect(() => {
    if (isMobile) router.replace("/chat");
  }, [isMobile, router]);

  if (isMobile) return null;

  return (
    <Group orientation="horizontal" className="h-full">
      {/* File Tree (collapsible) */}
      {showFileTree && (
        <>
          <Panel defaultSize="15%" minSize="10%" maxSize="30%">
            <FileTree />
          </Panel>
          <Separator className="w-1 bg-[var(--chat-border)] hover:bg-[var(--chat-accent)] transition-colors" />
        </>
      )}

      {/* Editor + Chat stacked */}
      <Panel defaultSize={showFileTree ? "50%" : "60%"} minSize="30%">
        <Group orientation="vertical">
          {/* Editor pane */}
          <Panel defaultSize="65%" minSize="20%">
            <EditorPane />
          </Panel>

          <Separator className="h-1 bg-[var(--chat-border)] hover:bg-[var(--chat-accent)] transition-colors" />

          {/* Chat pane */}
          <Panel defaultSize="35%" minSize="20%">
            <ChatView showDevContext />
          </Panel>
        </Group>
      </Panel>

      <Separator className="w-1 bg-[var(--chat-border)] hover:bg-[var(--chat-accent)] transition-colors" />

      {/* Terminal + Preview stacked */}
      <Panel defaultSize="35%" minSize="20%">
        <Group orientation="vertical">
          {/* Terminal pane with tabs */}
          <Panel defaultSize={showOutputPreview ? "60%" : "100%"} minSize="30%">
            <TabbedTerminal />
          </Panel>

          {showOutputPreview && (
            <>
              <Separator className="h-1 bg-[var(--chat-border)] hover:bg-[var(--chat-accent)] transition-colors" />

              {/* Output preview */}
              <Panel defaultSize="40%" minSize="20%">
                <OutputPreview />
              </Panel>
            </>
          )}
        </Group>
      </Panel>
    </Group>
  );
}
