import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { TrainingRunHistory } from "@/components/training/training-run-history";

export default function TrainingRunsPage() {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-1 border-b border-[var(--chat-border)] bg-[var(--chat-surface)] px-6 py-2 text-xs text-[var(--chat-muted)]">
        <Link href="/training" className="hover:text-[var(--chat-text)] transition-colors">
          Training
        </Link>
        <ChevronRight size={12} />
        <span className="text-[var(--chat-text)]">Run History</span>
      </div>
      <TrainingRunHistory />
    </div>
  );
}
