"use client";

import type { FileAttachment } from "@/types/chat";
import { Paperclip, X } from "lucide-react";
import { useRef } from "react";
import { useFeaturePermissions } from "@/lib/hooks/use-feature-permissions";

interface InputToolbarProps {
  attachments: FileAttachment[];
  onAttachmentsChange: (attachments: FileAttachment[]) => void;
  disabled?: boolean;
}

export function InputToolbar({ attachments, onAttachmentsChange, disabled }: InputToolbarProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const { isAllowed } = useFeaturePermissions();
  const canAttachFiles = isAllowed("grounding_files");

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

      {/* Attachments use the same server-enforced feature policy as file grounding. */}
      <div className="flex items-center gap-1.5 px-4 py-1">
        {/* Attach */}
        <button
          type="button"
          disabled={disabled || !canAttachFiles}
          onClick={() => fileRef.current?.click()}
          className="inline-flex items-center gap-1.5 text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors disabled:opacity-40 mr-1"
          title={canAttachFiles ? "Attach file" : "File attachments are disabled by your administrator"}
        >
          <Paperclip size={13} />
        </button>
        <input ref={fileRef} type="file" multiple hidden onChange={handleFileChange} />

      </div>
    </div>
  );
}
