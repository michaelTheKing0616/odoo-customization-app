"use client";

import { useEffect, useState } from "react";

const DEFAULT_PHRASE = "I understand the risks";

export type ConfirmDialogProps = {
  open: boolean;
  title: string;
  warning: string;
  risks: string[];
  phrase?: string;
  onConfirm: (phrase: string) => void;
  onCancel: () => void;
  busy?: boolean;
};

export function ConfirmDialog({
  open,
  title,
  warning,
  risks,
  phrase = DEFAULT_PHRASE,
  onConfirm,
  onCancel,
  busy = false,
}: ConfirmDialogProps) {
  const [typed, setTyped] = useState("");

  useEffect(() => {
    if (open) setTyped("");
  }, [open]);

  if (!open) return null;

  const canConfirm = typed === phrase && !busy;

  return (
    <div
      data-testid="confirm-dialog"
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#0c090b]/80 px-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
    >
      <div className="w-full max-w-lg border border-[#a85b4a] bg-[#2a1512] p-5 shadow-lg">
        <h2
          id="confirm-dialog-title"
          className="font-[family-name:var(--font-display)] text-xl text-[#f0a8a0]"
        >
          {title}
        </h2>
        <p className="mt-2 text-sm text-[#e8cfc9]">{warning}</p>
        {risks.length > 0 && (
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-[#e8cfc9]">
            {risks.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        )}
        <label className="mt-4 block text-sm">
          <span className="text-[#e8cfc9]">
            Type <code className="text-[#f0a8a0]">{phrase}</code> to continue
          </span>
          <input
            data-testid="confirm-dialog-input"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            disabled={busy}
            autoFocus
            className="mt-1 w-full border border-[#5a3a36] bg-[#0c090b] px-3 py-2 text-[#f4eef2] outline-none focus:border-[#f0a8a0]"
          />
        </label>
        <div className="mt-4 flex gap-3">
          <button
            type="button"
            data-testid="confirm-dialog-cancel"
            className="border border-[#8f7a88] px-4 py-2 text-sm text-[#d4c4ce]"
            onClick={onCancel}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="button"
            data-testid="confirm-dialog-confirm"
            disabled={!canConfirm}
            className="bg-[#a85b4a] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            onClick={() => onConfirm(phrase)}
          >
            {busy ? "Working…" : "Confirm"}
          </button>
        </div>
      </div>
    </div>
  );
}
