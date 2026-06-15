"use client";

import type { FileAttachment } from "@/types/chat";
import { Paperclip, X, Brain, Search, Zap } from "lucide-react";
import { Fragment, useRef } from "react";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { cn } from "@/lib/utils/cn";
import { FeatureCalloutBadge } from "@/components/onboarding/FeatureCalloutBadge";
import type { FeatureKey } from "@/lib/onboarding/feature-registry";

interface InputToolbarProps {
  attachments: FileAttachment[];
  onAttachmentsChange: (attachments: FileAttachment[]) => void;
  disabled?: boolean;
}

export function InputToolbar({ attachments, onAttachmentsChange, disabled }: InputToolbarProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const groundingDocs = useSettingsStore((s) => s.groundingDocs);
  const setGroundingDocs = useSettingsStore((s) => s.setGroundingDocs);
  const researchMode = useSettingsStore((s) => s.researchMode);
  const setResearchMode = useSettingsStore((s) => s.setResearchMode);
  const swarmMode = useSettingsStore((s) => s.swarmMode);
  const setSwarmMode = useSettingsStore((s) => s.setSwarmMode);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    Promise.all(
      files.map(
        (f) =>
          new Promise<FileAttachment>((resolve) => {
            const reader = new FileReader();
            reader.onload = () => {
              const base64 = (reader.result as string).split(",")[1] ?? "";
              resolve({ name: f.name, mimeType: f.type, data: base64, size: f.size });
            };
            reader.readAsDataURL(f);
          })
      )
    ).then((newAttachments) => {
      onAttachmentsChange([...attachments, ...newAttachments]);
    });
    e.target.value = "";
  };

  const removeAttachment = (name: string) => {
    onAttachmentsChange(attachments.filter((a) => a.name !== name));
  };

  const chips: Array<{
    key: string;
    label: string;
    icon: typeof Brain;
    active: boolean;
    onToggle: () => void;
    feature?: FeatureKey;
  }> = [
    {
      key: "memory",
      label: "Memory",
      icon: Brain,
      active: groundingDocs,
      onToggle: () => setGroundingDocs(!groundingDocs),
    },
    {
      key: "research",
      label: "Research",
      icon: Search,
      active: researchMode,
      onToggle: () => setResearchMode(!researchMode),
      feature: "research_v1",
    },
    {
      key: "swarm",
      label: "Swarm",
      icon: Zap,
      active: swarmMode,
      onToggle: () => setSwarmMode(!swarmMode),
      feature: "swarm_v1",
    },
  ];

  return (
    <div className="flex flex-col gap-1 max-w-5xl mx-auto w-full">
      {/* Attachment chips */}
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2 px-4 pt-2">
          {attachments.map((a) => (
            <span
              key={a.name}
              className="inline-flex items-center gap-1.5 text-xs bg-[var(--chat-panel)] border border-[var(--chat-border)] text-[var(--chat-text)] rounded-md px-2 py-1"
            >
              {a.name}
              <button type="button" onClick={() => removeAttachment(a.name)} className="hover:text-red-400">
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Mode chips + attach button row */}
      <div className="flex items-center gap-1.5 px-4 py-1">
        {/* Attach */}
        <button
          type="button"
          disabled={disabled}
          onClick={() => fileRef.current?.click()}
          className="inline-flex items-center gap-1.5 text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors disabled:opacity-40 mr-1"
          title="Attach file"
        >
          <Paperclip size={13} />
        </button>
        <input ref={fileRef} type="file" multiple hidden onChange={handleFileChange} />

        {/* Divider */}
        <div className="w-px h-4 bg-[var(--chat-border)] mx-0.5" />

        {/* Mode chips */}
        {chips.map(({ key, label, icon: Icon, active, onToggle, feature }) => {
          const button = (
            <button
              type="button"
              disabled={disabled}
              onClick={onToggle}
              className={cn(
                "inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full border transition-all",
                active
                  ? "bg-[color:color-mix(in_srgb,var(--chat-accent)_15%,transparent)] border-[color:color-mix(in_srgb,var(--chat-accent)_50%,transparent)] text-[var(--chat-accent)]"
                  : "border-[var(--chat-border)] text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:border-[color:color-mix(in_srgb,var(--chat-border)_80%,var(--chat-text))]"
              )}
            >
              <Icon size={10} />
              {label}
            </button>
          );
          return feature ? (
            <FeatureCalloutBadge key={key} feature={feature}>
              {button}
            </FeatureCalloutBadge>
          ) : (
            <Fragment key={key}>{button}</Fragment>
          );
        })}
      </div>
    </div>
  );
}
