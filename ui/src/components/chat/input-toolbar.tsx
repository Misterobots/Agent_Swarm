"use client";

import type { FileAttachment } from "@/types/chat";
import { Paperclip, X } from "lucide-react";
import { useRef } from "react";

interface InputToolbarProps {
  attachments: FileAttachment[];
  onAttachmentsChange: (attachments: FileAttachment[]) => void;
  disabled?: boolean;
}

export function InputToolbar({ attachments, onAttachmentsChange, disabled }: InputToolbarProps) {
  const fileRef = useRef<HTMLInputElement>(null);

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

  if (attachments.length === 0) {
    return (
      <div className="flex px-4 py-1 max-w-3xl mx-auto w-full">
        <button
          type="button"
          disabled={disabled}
          onClick={() => fileRef.current?.click()}
          className="inline-flex items-center gap-1.5 text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors disabled:opacity-40"
        >
          <Paperclip size={13} />
          Attach
        </button>
        <input ref={fileRef} type="file" multiple hidden onChange={handleFileChange} />
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-2 px-4 py-2 max-w-3xl mx-auto w-full">
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
      <button
        type="button"
        disabled={disabled}
        onClick={() => fileRef.current?.click()}
        className="inline-flex items-center gap-1 text-xs text-[var(--chat-muted)] hover:text-[var(--chat-text)] transition-colors disabled:opacity-40"
      >
        <Paperclip size={13} />
      </button>
      <input ref={fileRef} type="file" multiple hidden onChange={handleFileChange} />
    </div>
  );
}
