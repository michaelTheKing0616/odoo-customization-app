"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";

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

/** @deprecated Prefer ConfirmDialogV2 for new code — kept for existing callers. */
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
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 px-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
    >
      <div className="w-full max-w-lg rounded-md border border-danger/40 bg-danger-subtle p-5 shadow-overlay">
        <h2
          id="confirm-dialog-title"
          className="font-[family-name:var(--font-display)] text-xl text-danger"
        >
          {title}
        </h2>
        <p className="mt-2 text-sm text-ink">{warning}</p>
        {risks.length > 0 && (
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-ink">
            {risks.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        )}
        <label className="mt-4 block text-sm">
          <span className="text-muted">
            Type <code className="font-mono text-danger">{phrase}</code> to continue
          </span>
          <input
            data-testid="confirm-dialog-input"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            disabled={busy}
            autoFocus
            className="mt-1 w-full rounded-md border border-border-subtle bg-surface px-3 py-2 text-ink outline-none focus-visible:ring-2 focus-visible:ring-danger focus-visible:ring-offset-2"
          />
        </label>
        <div className="mt-4 flex gap-3">
          <Button
            type="button"
            variant="secondary"
            size="md"
            data-testid="confirm-dialog-cancel"
            onClick={onCancel}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="danger"
            size="md"
            data-testid="confirm-dialog-confirm"
            disabled={!canConfirm}
            loading={busy}
            onClick={() => onConfirm(phrase)}
          >
            Confirm
          </Button>
        </div>
      </div>
    </div>
  );
}
