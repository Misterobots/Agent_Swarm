"use client";

import { Wrench } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useSettingsStore } from "@/lib/stores/settings-store";
import type { Skill } from "@/types/chat";

const SKILLS: { value: Skill; label: string }[] = [
  { value: "general", label: "General" },
  { value: "code", label: "Code" },
  { value: "devops", label: "DevOps" },
  { value: "data", label: "Data" },
  { value: "creative", label: "Creative" },
  { value: "research", label: "Research" },
  { value: "explain", label: "Explain" },
];

export function SkillSelector() {
  const skill = useSettingsStore((s) => s.skill);
  const setSkill = useSettingsStore((s) => s.setSkill);

  return (
    <div className="relative inline-flex items-center">
      <Wrench size={14} className="absolute left-2 pointer-events-none text-[var(--chat-muted)]" />
      <select
        value={skill}
        onChange={(e) => setSkill(e.target.value as Skill)}
        className={cn(
          "appearance-none pl-7 pr-6 py-1.5 rounded-md text-xs border cursor-pointer",
          "bg-[var(--chat-panel)] text-[var(--chat-text)] border-[var(--chat-border)]",
          "focus:border-[var(--chat-accent)] focus:outline-none",
          "hover:border-[var(--chat-accent)]",
          "transition-colors"
        )}
        title="Select skill focus"
      >
        {SKILLS.map((s) => (
          <option key={s.value} value={s.value}>
            {s.label}
          </option>
        ))}
      </select>
      <svg
        className="absolute right-1.5 pointer-events-none text-[var(--chat-muted)]"
        width="10"
        height="10"
        viewBox="0 0 10 10"
        fill="currentColor"
      >
        <path d="M2 3.5L5 7L8 3.5H2Z" />
      </svg>
    </div>
  );
}
