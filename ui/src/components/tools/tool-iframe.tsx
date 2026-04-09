"use client";

import { useState } from "react";
import { Loader2, AlertTriangle } from "lucide-react";

interface ToolIframeProps {
  url: string;
  label: string;
}

export function ToolIframe({ url, label }: ToolIframeProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  return (
    <div className="relative flex-1">
      {loading && !error && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#0a0a14]">
          <div className="flex flex-col items-center gap-3">
            <Loader2 size={24} className="text-cyan-400 animate-spin" />
            <span className="text-sm text-zinc-500">Loading {label}...</span>
          </div>
        </div>
      )}

      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#0a0a14]">
          <div className="flex flex-col items-center gap-3">
            <AlertTriangle size={24} className="text-red-400" />
            <span className="text-sm text-red-300">Failed to load {label}</span>
            <span className="text-xs text-zinc-500">The service may be unavailable or blocking iframe embedding.</span>
          </div>
        </div>
      )}

      <iframe
        src={url}
        title={label}
        className="w-full h-full border-0"
        style={{ height: "calc(100vh - 6.5rem)" }}
        sandbox="allow-same-origin allow-scripts allow-popups allow-forms allow-downloads"
        onLoad={() => setLoading(false)}
        onError={() => {
          setLoading(false);
          setError(true);
        }}
      />
    </div>
  );
}
