"use client";

import { useRef, useCallback } from "react";
import { Paperclip, X } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import type { FileAttachment } from "@/types/chat";

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB
const ACCEPTED_TYPES = [
  "image/png", "image/jpeg", "image/gif", "image/webp",
  "text/plain", "text/csv", "application/json",
  "application/pdf",
];

interface FileUploadButtonProps {
  attachments: FileAttachment[];
  onAttach: (file: FileAttachment) => void;
  onRemove: (index: number) => void;
  disabled?: boolean;
}

export function FileUploadButton({ attachments, onAttach, onRemove, disabled }: FileUploadButtonProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (!files) return;

      for (const file of Array.from(files)) {
        if (file.size > MAX_FILE_SIZE) {
          console.error(`File too large: ${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)`);
          continue;
        }
        if (!ACCEPTED_TYPES.includes(file.type)) {
          console.error(`Unsupported file type: ${file.type} for ${file.name}`);
          continue;
        }

        const buffer = await file.arrayBuffer();
        const bytes = new Uint8Array(buffer);
        let binary = "";
        for (let i = 0; i < bytes.byteLength; i++) {
          binary += String.fromCharCode(bytes[i]);
        }
        const base64 = btoa(binary);

        onAttach({
          name: file.name,
          mimeType: file.type,
          data: base64,
          size: file.size,
        });
      }

      // Reset input so the same file can be re-selected
      if (inputRef.current) inputRef.current.value = "";
    },
    [onAttach]
  );

  return (
    <div className="flex items-center gap-1.5">
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPTED_TYPES.join(",")}
        className="hidden"
        onChange={handleFileChange}
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={disabled}
        className={cn(
          "p-1.5 rounded-md transition-colors",
          disabled
            ? "text-[var(--chat-muted)] cursor-not-allowed"
            : "text-[var(--chat-muted)] hover:text-[var(--chat-text)] hover:bg-[var(--chat-soft)]"
        )}
        title="Attach file"
      >
        <Paperclip size={16} />
      </button>

      {attachments.map((att, idx) => (
        <span
          key={`${att.name}-${idx}`}
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] bg-[var(--chat-soft)] text-[var(--chat-text)] border border-[var(--chat-border)]"
        >
          {att.mimeType.startsWith("image/") ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={`data:${att.mimeType};base64,${att.data}`}
              alt={att.name}
              className="w-4 h-4 rounded object-cover"
            />
          ) : null}
          <span className="max-w-[80px] truncate">{att.name}</span>
          <button
            type="button"
            onClick={() => onRemove(idx)}
            className="text-[var(--chat-muted)] hover:text-[var(--chat-text)]"
          >
            <X size={10} />
          </button>
        </span>
      ))}
    </div>
  );
}
