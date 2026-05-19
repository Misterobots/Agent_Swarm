import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { TrainingRunHistory } from "@/components/training/training-run-history";

export default function TrainingRunsPage() {
  return (
    <div className="flex h-full flex-col">
      <div
        className="relative flex items-center gap-1.5 bg-[var(--chat-surface)] py-2.5 text-[12px]"
        style={{ paddingLeft: "calc(var(--sidebar-rail-pad, 0px) + 1.5rem)", paddingRight: "1.5rem" }}
      >
        <Link href="/training" className="text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors">
          Training
        </Link>
        <ChevronRight size={12} className="text-[var(--chat-subtle)]" />
        <span className="text-[var(--chat-text)] font-medium">Run History</span>
        <div className="absolute bottom-0 left-0 right-0 divider" />
      </div>
      <TrainingRunHistory />
    </div>
  );
}
