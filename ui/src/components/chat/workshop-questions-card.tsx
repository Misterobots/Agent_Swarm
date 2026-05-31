"use client";

import { useState, useRef, useEffect } from "react";
import { ClipboardList, ChevronDown, Send } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import type { WorkshopQuestion } from "@/types/chat";

interface WorkshopQuestionsCardProps {
  questions: WorkshopQuestion[];
  onSend?: (text: string) => void;
}

export function WorkshopQuestionsCard({ questions, onSend }: WorkshopQuestionsCardProps) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const textareaRefs = useRef<Record<number, HTMLTextAreaElement | null>>({});

  // Auto-focus textarea when a question expands
  useEffect(() => {
    if (expanded !== null) {
      setTimeout(() => textareaRefs.current[expanded]?.focus(), 50);
    }
  }, [expanded]);

  const toggle = (n: number) => setExpanded((prev) => (prev === n ? null : n));

  const handleAnswer = (n: number, value: string) =>
    setAnswers((prev) => ({ ...prev, [n]: value }));

  const submitOne = (q: WorkshopQuestion) => {
    const answer = (answers[q.number] ?? "").trim();
    if (!answer || !onSend) return;
    onSend(`Q${q.number} (${q.topic}): ${answer}`);
    setExpanded(null);
  };

  const submitAll = () => {
    if (!onSend) return;
    const answered = questions.filter((q) => (answers[q.number] ?? "").trim());
    if (answered.length > 0) {
      onSend(answered.map((q) => `Q${q.number} (${q.topic}): ${answers[q.number].trim()}`).join("\n\n"));
    } else {
      // No answers yet — send blank template so user can fill in chat
      onSend(questions.map((q) => `Q${q.number} (${q.topic}): `).join("\n"));
    }
  };

  const answeredCount = questions.filter((q) => (answers[q.number] ?? "").trim()).length;

  return (
    <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-950/10 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-amber-500/20">
        <ClipboardList size={14} className="text-amber-400 shrink-0" />
        <span className="text-xs font-medium text-amber-300">
          {questions.length} Discovery Questions
        </span>
        <span className="text-xs text-amber-500/60 ml-1">— click any to answer</span>
        {answeredCount > 0 && (
          <button
            type="button"
            onClick={submitAll}
            className="ml-auto flex items-center gap-1 text-xs text-amber-400 hover:text-amber-200 transition-colors font-medium"
          >
            <Send size={11} />
            Submit {answeredCount} answer{answeredCount > 1 ? "s" : ""}
          </button>
        )}
        {answeredCount === 0 && (
          <button
            type="button"
            onClick={submitAll}
            className="ml-auto text-xs text-amber-500/70 hover:text-amber-300 transition-colors"
          >
            answer all at once →
          </button>
        )}
      </div>

      {/* Question list */}
      <div className="divide-y divide-amber-500/10">
        {questions.map((q) => {
          const isOpen = expanded === q.number;
          const answer = answers[q.number] ?? "";
          const hasAnswer = answer.trim().length > 0;

          return (
            <div key={q.number}>
              {/* Chip row */}
              <button
                type="button"
                onClick={() => toggle(q.number)}
                className={cn(
                  "w-full flex items-center gap-2.5 px-3 py-2.5 text-left transition-colors",
                  isOpen
                    ? "bg-amber-900/30"
                    : "hover:bg-amber-950/30",
                )}
              >
                <span className={cn(
                  "shrink-0 w-5 h-5 rounded-full text-[10px] font-bold flex items-center justify-center transition-colors",
                  hasAnswer
                    ? "bg-amber-500/60 text-amber-100"
                    : isOpen
                      ? "bg-amber-500/30 text-amber-300"
                      : "bg-amber-500/20 text-amber-400",
                )}>
                  {q.number}
                </span>
                <span className="flex-1 min-w-0">
                  <span className={cn(
                    "text-xs font-semibold block leading-tight",
                    hasAnswer ? "text-amber-200" : "text-amber-300",
                  )}>
                    {q.topic}
                    {hasAnswer && <span className="ml-1.5 text-amber-500/70 font-normal">✓</span>}
                  </span>
                  {!isOpen && (
                    <span className="text-[11px] text-amber-400/60 leading-snug line-clamp-1 block">
                      {hasAnswer ? answer : q.text}
                    </span>
                  )}
                </span>
                <ChevronDown
                  size={13}
                  className={cn(
                    "shrink-0 text-amber-500/50 transition-transform duration-200",
                    isOpen && "rotate-180",
                  )}
                />
              </button>

              {/* Expanded answer area */}
              {isOpen && (
                <div className="px-3 pb-3 bg-amber-900/20">
                  <p className="text-[12px] text-amber-300/80 leading-relaxed mb-2 pt-1">
                    {q.text}
                  </p>
                  <textarea
                    ref={(el) => { textareaRefs.current[q.number] = el; }}
                    value={answer}
                    onChange={(e) => handleAnswer(q.number, e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                        e.preventDefault();
                        submitOne(q);
                      }
                    }}
                    placeholder="Type your answer…"
                    rows={3}
                    className={cn(
                      "w-full rounded-md px-3 py-2 text-xs resize-none outline-none transition-colors",
                      "bg-amber-950/40 border border-amber-500/30 text-amber-100 placeholder-amber-600/50",
                      "focus:border-amber-500/60 focus:bg-amber-950/60",
                    )}
                  />
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-[10px] text-amber-600/50">⌘↵ to submit</span>
                    <button
                      type="button"
                      onClick={() => submitOne(q)}
                      disabled={!answer.trim() || !onSend}
                      className={cn(
                        "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                        answer.trim() && onSend
                          ? "bg-amber-500/30 text-amber-200 hover:bg-amber-500/50 border border-amber-500/40"
                          : "bg-amber-950/30 text-amber-600/40 border border-amber-500/20 cursor-not-allowed",
                      )}
                    >
                      <Send size={11} />
                      Submit answer
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
