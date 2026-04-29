"use client";

import { useState, useEffect } from "react";
import { Panel, Group, Separator } from "react-resizable-panels";
import { ChatView } from "@/components/chat/chat-view";
import { TabbedEditor } from "./tabbed-editor";
import { TabbedTerminal } from "./tabbed-terminal";
import { FileTree } from "./file-tree";
import { DevOpsPanel } from "./devops-panel";
import { GitPanel } from "./git-panel";
import { LogViewer } from "./log-viewer";
import { QuickActionsToolbar } from "./quick-actions-toolbar";
import { useRouter } from "next/navigation";
import { useIsMobile } from "@/lib/hooks/use-mobile";
import { useDevStore } from "@/lib/stores/dev-store";

type RightPanelView = "devops" | "git" | "logs";

export function DevWorkspace() {
  const { isMobile } = useIsMobile();
  const router = useRouter();
  const { showFileTree } = useDevStore();
  const [rightPanelView, setRightPanelView] = useState<RightPanelView>("devops");
  const [showRightPanel, setShowRightPanel] = useState(true);

  // Redirect to chat on mobile — Dev workspace is desktop-only
  useEffect(() => {
    if (isMobile) router.replace("/chat");
  }, [isMobile, router]);

  if (isMobile) return null;

  return (
    <div className="flex flex-col h-full">
      {/* Quick Actions Toolbar */}
      <QuickActionsToolbar />

      {/* Main Workspace */}
      <div className="flex-1 overflow-hidden">
        <Group orientation="horizontal" className="h-full">
          {/* Left Sidebar: File Tree */}
          {showFileTree && (
            <>
              <Panel defaultSize={15} minSize={10} maxSize={25}>
                <FileTree />
              </Panel>
              <Separator className="w-1 bg-[var(--chat-border)] hover:bg-[var(--chat-accent)] transition-colors" />
            </>
          )}

          {/* Center: Editor + Terminal + Chat */}
          <Panel defaultSize={showFileTree ? 55 : 65} minSize={35}>
            <Group orientation="vertical">
              {/* Editor */}
              <Panel defaultSize={45} minSize={20}>
                <TabbedEditor />
              </Panel>

              <Separator className="h-1 bg-[var(--chat-border)] hover:bg-[var(--chat-accent)] transition-colors" />

              {/* Terminal */}
              <Panel defaultSize={30} minSize={15}>
                <TabbedTerminal />
              </Panel>

              <Separator className="h-1 bg-[var(--chat-border)] hover:bg-[var(--chat-accent)] transition-colors" />

              {/* Chat */}
              <Panel defaultSize={25} minSize={15}>
                <ChatView showDevContext />
              </Panel>
            </Group>
          </Panel>

          {/* Right Sidebar: DevOps/Git/Logs */}
          {showRightPanel && (
            <>
              <Separator className="w-1 bg-[var(--chat-border)] hover:bg-[var(--chat-accent)] transition-colors" />
              <Panel defaultSize={30} minSize={20} maxSize={40}>
                <div className="flex flex-col h-full">
                  {/* Tab Switcher */}
                  <div className="flex items-center border-b border-[var(--chat-border)] bg-[var(--chat-bg)]">
                    <button
                      onClick={() => setRightPanelView("devops")}
                      className={`flex-1 px-4 py-2 text-xs font-medium transition-colors ${
                        rightPanelView === "devops"
                          ? "text-[var(--chat-accent)] border-b-2 border-[var(--chat-accent)] bg-[var(--chat-input-bg)]"
                          : "text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--chat-hover)]"
                      }`}
                    >
                      DevOps
                    </button>
                    <button
                      onClick={() => setRightPanelView("git")}
                      className={`flex-1 px-4 py-2 text-xs font-medium transition-colors ${
                        rightPanelView === "git"
                          ? "text-[var(--chat-accent)] border-b-2 border-[var(--chat-accent)] bg-[var(--chat-input-bg)]"
                          : "text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--chat-hover)]"
                      }`}
                    >
                      Git
                    </button>
                    <button
                      onClick={() => setRightPanelView("logs")}
                      className={`flex-1 px-4 py-2 text-xs font-medium transition-colors ${
                        rightPanelView === "logs"
                          ? "text-[var(--chat-accent)] border-b-2 border-[var(--chat-accent)] bg-[var(--chat-input-bg)]"
                          : "text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--chat-hover)]"
                      }`}
                    >
                      Logs
                    </button>
                  </div>

                  {/* Panel Content */}
                  <div className="flex-1 overflow-hidden">
                    {rightPanelView === "devops" && <DevOpsPanel />}
                    {rightPanelView === "git" && <GitPanel />}
                    {rightPanelView === "logs" && <LogViewer />}
                  </div>
                </div>
              </Panel>
            </>
          )}
        </Group>
      </div>
    </div>
  );
}
