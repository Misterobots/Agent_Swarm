"use client";

import { ClipboardList } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useSettingsStore } from "@/lib/stores/settings-store";
import type { WorkshopQuestion } from "@/types/chat";

interface WorkshopQuestionsCardProps {
  questions: WorkshopQuestion[];
}

export function WorkshopQuestionsCard({ questions }: WorkshopQuestionsCardProps) {
  const setPendingInput = useSettingsStore((s) => s.setPendingInput);

  const handleQuestionClick = (q: WorkshopQuestion) => {
    setPendingInput(`Q${q.number} (${q.topic}): `);
  };

  const handleAnswerAll = () => {
    const template = questions
      .map((q) => `Q${q.number} (${q.topic}): `)
      .join("\n");
    setPendingInput(template);
  };

  return (
    <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-950/10 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-amber-500/20">
        <ClipboardList size={14} className="text-amber-400 shrink-0" />
        <span className="text-xs font-medium text-amber-300">
          {questions.length} Discovery Questions
        </span>
        <span className="text-xs text-amber-500/70 ml-1">
          — click any to answer, or
        </span>
        <button
          type="button"
          onClick={handleAnswerAll}
          className="ml-auto text-xs text-amber-400 hover:text-amber-200 transition-colors underline underline-offset-2"
        >
          answer all at once
        </button>
      </div>

      {/* Question chips grid */}
      <div className="p-2 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
        {questions.map((q) => (
          <button
            key={q.number}
            type="button"
            onClick={() => handleQuestionClick(q)}
            title={q.text}
            className={cn(
              "group flex items-start gap-2 w-full text-left px-2.5 py-2",
              "rounded-md border text-xs transition-all",
              "border-amber-500/20 bg-amber-950/20 hover:bg-amber-950/40",
              "hover:border-amber-500/50 hover:text-amber-200",
              "text-amber-300/80"
            )}
          >
            <span className="shrink-0 w-5 h-5 rounded-full bg-amber-500/20 text-amber-400 text-[10px] font-bold flex items-center justify-center mt-0.5 group-hover:bg-amber-500/40">
              {q.number}
            </span>
            <span className="flex flex-col gap-0.5 min-w-0">
              <span className="font-semibold leading-tight">{q.topic}</span>
              <span className="text-amber-400/60 text-[11px] leading-snug line-clamp-2 group-hover:text-amber-400/90">
                {q.text}
              </span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
