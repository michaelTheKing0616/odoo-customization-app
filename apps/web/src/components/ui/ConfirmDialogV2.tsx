"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

const DEFAULT_PHRASE = "I understand the risks";

export type ConfirmDialogV2Props = {
  open: boolean;
  title: string;
  warning: string;
  risks: string[];
  phrase?: string;
  onConfirm: (phrase: string) => void;
  onCancel: () => void;
  busy?: boolean;
  riskLevel?: "standard" | "danger";
  snapshotNote?: string;
};

/**
 * Phrase-confirm dialog — standard (neutral) or danger (red header + consequences).
 * Danger level surfaces snapshot guidance as a highlighted line below the risk list.
 */
export function ConfirmDialogV2({
  open,
  title,
  warning,
  risks,
  phrase = DEFAULT_PHRASE,
  onConfirm,
  onCancel,
  busy = false,
  riskLevel = "standard",
  snapshotNote,
}: ConfirmDialogV2Props) {
  const [typed, setTyped] = useState("");
  const danger = riskLevel === "danger";

  useEffect(() => {
    if (open) setTyped("");
  }, [open]);

  if (!open) return null;

  const canConfirm = typed === phrase && !busy;

  return (
    <div
      data-testid="confirm-dialog-v2"
      data-risk-level={riskLevel}
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 px-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-v2-title"
    >
      <div
        className={cn(
          "w-full max-w-lg overflow-hidden rounded-md border shadow-overlay",
          danger ? "border-danger/40 bg-surface-raised" : "border-border-subtle bg-surface-raised",
        )}
      >
        <div
          className={cn(
            "px-5 py-4",
            danger ? "border-b border-danger/30 bg-danger-subtle" : "border-b border-border-subtle",
          )}
          data-testid="confirm-dialog-v2-header"
        >
          <h2
            id="confirm-dialog-v2-title"
            className={cn(
              "font-[family-name:var(--font-display)] text-xl",
              danger ? "text-danger" : "text-ink",
            )}
          >
            {title}
          </h2>
        </div>

        <div className="space-y-3 px-5 py-4">
          <p className="text-sm text-muted">{warning}</p>

          {risks.length > 0 && (
            <ul
              className="list-disc space-y-1 pl-5 text-sm text-ink"
              data-testid="confirm-dialog-v2-risks"
            >
              {risks.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          )}

          {danger && snapshotNote ? (
            <p
              className="rounded-md border border-danger/30 bg-danger-subtle px-3 py-2 text-sm text-ink"
              data-testid="confirm-dialog-v2-snapshot"
            >
              {snapshotNote}
            </p>
          ) : null}

          <label className="block text-sm">
            <span className="text-muted">
              Type <code className="font-mono text-accent">{phrase}</code> to continue
            </span>
            <input
              data-testid="confirm-dialog-v2-input"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              disabled={busy}
              autoFocus
              className="mt-1 w-full rounded-md border border-border-subtle bg-surface px-3 py-2 text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
            />
          </label>

          <div className="flex gap-3 pt-1">
            <Button
              type="button"
              variant="secondary"
              size="md"
              data-testid="confirm-dialog-v2-cancel"
              onClick={onCancel}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant={danger ? "danger" : "primary"}
              size="md"
              data-testid="confirm-dialog-v2-confirm"
              disabled={!canConfirm}
              loading={busy}
              onClick={() => onConfirm(phrase)}
            >
              Confirm
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
