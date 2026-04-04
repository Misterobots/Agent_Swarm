"use client";

import { useCallback } from "react";
import type { FileAttachment } from "@/types/chat";
import { FileUploadButton } from "./file-upload-button";
import { ResearchToggle } from "./research-toggle";
import { SkillSelector } from "./skill-selector";
import { StyleSelector } from "./style-selector";

interface InputToolbarProps {
  attachments: FileAttachment[];
  onAttachmentsChange: (attachments: FileAttachment[]) => void;
  disabled?: boolean;
}

export function InputToolbar({ attachments, onAttachmentsChange, disabled }: InputToolbarProps) {
  const handleAttach = useCallback(
    (file: FileAttachment) => {
      onAttachmentsChange([...attachments, file]);
    },
    [attachments, onAttachmentsChange]
  );

  const handleRemove = useCallback(
    (index: number) => {
      onAttachmentsChange(attachments.filter((_, i) => i !== index));
    },
    [attachments, onAttachmentsChange]
  );

  return (
    <div className="flex items-center gap-2 flex-wrap px-4 py-1.5 border-t border-[var(--chat-border)] bg-[var(--chat-surface)]">
      <FileUploadButton
        attachments={attachments}
        onAttach={handleAttach}
        onRemove={handleRemove}
        disabled={disabled}
      />
      <div className="w-px h-5 bg-[var(--chat-border)]" />
      <ResearchToggle />
      <SkillSelector />
      <StyleSelector />
    </div>
  );
}
