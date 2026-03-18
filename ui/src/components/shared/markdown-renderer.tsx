"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CodeBlock } from "./code-block";
import type { Components } from "react-markdown";

interface MarkdownRendererProps {
  content: string;
}

const components: Components = {
  code({ className, children, ...props }) {
    const match = /language-(\w+)/.exec(className || "");
    const isInline = !match && !className;

    if (isInline) {
      return (
        <code className="bg-[#1a1a2e] text-cyan-300 px-1.5 py-0.5 rounded text-sm" {...props}>
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
  table({ children }) {
    return (
      <div className="overflow-x-auto my-3">
        <table className="min-w-full border-collapse border border-zinc-700 text-sm">
          {children}
        </table>
      </div>
    );
  },
  th({ children }) {
    return (
      <th className="border border-zinc-700 bg-[#1a1a2e] px-3 py-2 text-left text-zinc-300">
        {children}
      </th>
    );
  },
  td({ children }) {
    return (
      <td className="border border-zinc-700 px-3 py-2 text-zinc-400">
        {children}
      </td>
    );
  },
};

export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return (
    <div className="prose prose-invert prose-sm max-w-none prose-p:my-2 prose-headings:my-3 prose-li:my-0.5 prose-pre:p-0 prose-pre:bg-transparent">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
