/**
 * Memex Desktop bridge — mirrors the window.claude pattern from Claude Desktop.
 *
 * The Electron preload (preload-memex.ts) injects window.memex when running
 * inside the native app. All calls here are safe to use in both browser and
 * desktop contexts — they no-op gracefully when not in the app.
 */

export interface MemexDesktopBridge {
  isDesktop: boolean;
  version: () => Promise<string>;

  fs: {
    readFile:  (path: string) => Promise<string>;
    writeFile: (path: string, content: string) => Promise<void>;
    readDir:   (path: string) => Promise<Array<{ name: string; path: string; isDir: boolean }>>;
    mkdir:     (path: string) => Promise<void>;
  };

  shell: {
    exec:         (cmd: string, cwd?: string) => Promise<{ stdout: string; stderr: string; code: number }>;
    openExternal: (url: string) => Promise<void>;
  };

  dialog: {
    openFolder: () => Promise<string | null>;
  };

  pty: {
    create:  (id: string, cwd?: string) => Promise<{ pid: number }>;
    write:   (id: string, data: string) => Promise<void>;
    resize:  (id: string, cols: number, rows: number) => Promise<void>;
    kill:    (id: string) => Promise<void>;
    onData:  (id: string, cb: (data: string) => void) => () => void;
    onExit:  (id: string, cb: (code: number) => void) => () => void;
  };

  onQuickSubmit: (cb: (text: string) => void) => void;
  onOpenPath:    (cb: (path: string) => void) => void;

  autoStart: {
    get: () => Promise<boolean>;
    set: (enable: boolean) => Promise<boolean>;
  };

  permissions: {
    request: (opts: {
      toolName:  string;
      toolInput: Record<string, unknown>;
      callId:    string;
    }) => Promise<{ approved: boolean; scope: "once" | "session" | "workspace" }>;
  };

  lsp: {
    start:   (ext: string, rootUri: string) => Promise<boolean>;
    request: (lang: string, rootUri: string, method: string, params: unknown) => Promise<unknown>;
    notify:  (lang: string, rootUri: string, method: string, params: unknown) => void;
    onNotification: (cb: (data: { lang: string; method: string; params: unknown }) => void) => () => void;
  };

  updater: {
    onStatus: (cb: (status: {
      state: "checking" | "available" | "downloading" | "ready" | "current" | "error";
      version?: string;
      percent?: number;
      message?: string;
    }) => void) => () => void;
    install: () => void;
  };
}

declare global {
  interface Window {
    memex?: MemexDesktopBridge;
  }
}

/** True when running inside the Memex Desktop Electron app. */
export const isDesktop = (): boolean =>
  typeof window !== "undefined" && window.memex?.isDesktop === true;

/** Safe accessor — returns the bridge or null in browser context. */
export const desktop = (): MemexDesktopBridge | null =>
  typeof window !== "undefined" ? (window.memex ?? null) : null;
