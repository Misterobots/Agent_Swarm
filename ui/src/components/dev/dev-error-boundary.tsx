"use client";

import React from "react";

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
}

export class DevErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("Dev Workspace Error:", error);
    console.error("Error Info:", errorInfo);
    console.error("Component Stack:", errorInfo.componentStack);
    
    this.setState({
      error,
      errorInfo,
    });

    // Send error to backend for logging (optional)
    fetch("/api/client-error", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        error: error.message,
        stack: error.stack,
        componentStack: errorInfo.componentStack,
        timestamp: new Date().toISOString(),
      }),
    }).catch(console.error);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full bg-[var(--chat-surface)] p-8">
          <div className="max-w-2xl w-full bg-red-900/20 border border-red-500/50 rounded-lg p-6">
            <h2 className="text-xl font-bold text-red-400 mb-4">
              Dev Workspace Error
            </h2>
            <p className="text-[var(--chat-text)] mb-4">
              An error occurred while rendering the dev workspace:
            </p>
            <pre className="bg-black/30 p-4 rounded text-sm text-red-300 overflow-auto max-h-64 mb-4">
              {this.state.error?.message}
              {"\n\n"}
              {this.state.error?.stack}
            </pre>
            <details className="mb-4">
              <summary className="cursor-pointer text-[var(--chat-muted)] hover:text-[var(--chat-text)]">
                Component Stack
              </summary>
              <pre className="bg-black/30 p-4 rounded text-xs text-[var(--chat-muted)] overflow-auto max-h-64 mt-2">
                {this.state.errorInfo?.componentStack}
              </pre>
            </details>
            <button
              onClick={() => {
                this.setState({
                  hasError: false,
                  error: null,
                  errorInfo: null,
                });
                window.location.reload();
              }}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded transition-colors"
            >
              Reload Page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
