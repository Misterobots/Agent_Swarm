"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CodeBlock } from "./code-block";
import { useStreamingText } from "@/lib/hooks/use-streaming-text";
import type { Components } from "react-markdown";

interface MarkdownRendererProps {
  content: string;
  isStreaming?: boolean;
}

const components: Components = {
  code({ className, children, ...props }) {
    const match = /language-(\w+)/.exec(className || "");
    const isInline = !match && !className;

    if (isInline) {
      return (
        <code className="bg-[var(--chat-soft)] text-[var(--chat-accent)] px-1 py-0.5 rounded text-[12px] font-mono" {...props}>
          {children}
        </code>
      );
    }

    return (
      <CodeBlock language={match?.[1]}>
        {String(children).replace(/\n$/, "")}
      </CodeBlock>
    );
  },
  h1({ children }) {
    return <h1 className="text-[15px] font-semibold text-[var(--chat-text)] mt-4 mb-1.5 pb-1 border-b border-[var(--chat-border)]">{children}</h1>;
  },
  h2({ children }) {
    return <h2 className="text-[14px] font-semibold text-[var(--chat-text)] mt-3 mb-1.5">{children}</h2>;
  },
  h3({ children }) {
    return <h3 className="text-[13px] font-semibold text-[var(--chat-text)] mt-2.5 mb-1">{children}</h3>;
  },
  p({ children }) {
    return <p className="text-[13px] leading-[1.65] my-1.5 text-[var(--chat-text)]">{children}</p>;
  },
  li({ children }) {
    return <li className="text-[13px] leading-[1.6] my-0.5">{children}</li>;
  },
  ul({ children }) {
    return <ul className="my-1.5 pl-4 list-disc marker:text-[var(--chat-muted)]">{children}</ul>;
  },
  ol({ children }) {
    return <ol className="my-1.5 pl-4 list-decimal marker:text-[var(--chat-muted)]">{children}</ol>;
  },
  blockquote({ children }) {
    return (
      <blockquote className="border-l-2 border-[var(--chat-accent)] pl-3 my-2 text-[var(--chat-muted)] text-[13px] leading-[1.6] not-italic">
        {children}
      </blockquote>
    );
  },
  hr() {
    return <hr className="border-[var(--chat-border)] my-3" />;
  },
  strong({ children }) {
    return <strong className="font-semibold text-[var(--chat-text)]">{children}</strong>;
  },
  table({ children }) {
    return (
      <div className="overflow-x-auto my-2">
        <table className="min-w-full border-collapse border border-[var(--chat-border)] text-[12px]">
          {children}
        </table>
      </div>
    );
  },
  th({ children }) {
    return (
      <th className="border border-[var(--chat-border)] bg-[var(--chat-soft)] px-2.5 py-1.5 text-left text-[var(--chat-text)] font-medium">
        {children}
      </th>
    );
  },
  td({ children }) {
    return (
      <td className="border border-[var(--chat-border)] px-2.5 py-1.5 text-[var(--chat-muted)]">
        {children}
      </td>
    );
  },
};

export function MarkdownRenderer({ content, isStreaming }: MarkdownRendererProps) {
  const { text: displayContent, isTyping } = useStreamingText(content, isStreaming ?? false);

  return (
    <div className="prose prose-invert max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 prose-pre:p-0 prose-pre:bg-transparent prose-pre:my-2">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {displayContent}
      </ReactMarkdown>
      {isTyping && (
        <span className="streaming-cursor inline-block ml-0.5 w-[2px] h-[13px] bg-[var(--chat-accent)] align-middle" aria-hidden="true" />
      )}
    </div>
  );
}
