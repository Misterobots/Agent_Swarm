"use client"

export default function OfflinePage() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-6 gap-6">
      <div className="w-16 h-16 rounded-2xl bg-[color:color-mix(in_srgb,var(--chat-accent)_14%,transparent)] flex items-center justify-center border border-[var(--chat-border)]">
        <svg width="28" height="32" viewBox="0 0 28 32" fill="none">
          <path
            d="M14 1L26 8V22L14 29L2 22V8L14 1Z"
            stroke="var(--chat-accent-strong, #fb923c)"
            strokeWidth="1.5"
            fill="color-mix(in srgb, var(--chat-accent, #f97316) 8%, transparent)"
          />
          <circle cx="14" cy="15" r="2.5" fill="var(--chat-accent-strong, #fb923c)" opacity="0.7" />
        </svg>
      </div>
      <div>
        <h1 className="text-xl font-semibold text-[var(--chat-text)] mb-2">
          You&apos;re Offline
        </h1>
        <p className="text-sm text-[var(--chat-muted)] max-w-xs mx-auto">
          Memex requires a network connection. Please check your connection and try again.
        </p>
      </div>
      <button
        onClick={() => window.location.reload()}
        className="px-4 py-2.5 rounded-md bg-[var(--chat-accent)] text-white text-sm font-medium hover:bg-[var(--chat-accent-strong)] transition-colors"
      >
        Retry Connection
      </button>
    </div>
  );
}
