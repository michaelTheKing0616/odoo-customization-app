"use client";

import { stakesFor, stakesLine } from "@/lib/stakes";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { DialogPanel } from "@/components/ui/Dialog";
import { cn } from "@/lib/cn";
import { useConfirmTarget } from "@/components/ui/useConfirmTarget";

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
  /** Concrete impact lines shown above risks (models, rules, records). */
  blastRadius?: string[];
};

/**
 * Phrase-confirm dialog — standard (neutral) or danger (red header + consequences).
 * Danger level surfaces snapshot guidance as a highlighted line below the risk list.
 * Overlay, Escape, and backdrop dismissal come from DialogPanel.
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
  blastRadius,
}: ConfirmDialogV2Props) {
  const [typed, setTyped] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const danger = riskLevel === "danger";

  useEffect(() => {
    if (open) setTyped("");
  }, [open]);

  const canConfirm = typed === phrase && !busy;

  // Touch 88: Cmd/Ctrl+Enter confirms the main action (still only once the phrase matches).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && canConfirm) {
        e.preventDefault();
        onConfirm(phrase);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, canConfirm, onConfirm, phrase]);

  const target = useConfirmTarget(open);
  return (
    <DialogPanel
      open={open}
      onOpenChange={(next) => {
        if (!next && !busy) onCancel();
      }}
      title={title}
      testId="confirm-dialog-v2"
      dataRiskLevel={riskLevel}
      headerTestId="confirm-dialog-v2-header"
      headerClassName={
        danger
          ? "-mx-5 -mt-5 border-b border-danger/30 bg-danger-subtle px-5 py-4"
          : "-mx-5 -mt-5 border-b border-border-subtle px-5 py-4"
      }
      titleClassName={cn("text-ui-display", danger ? "text-danger" : "text-ink")}
      initialFocus={inputRef}
      className={cn("overflow-hidden", danger && "border-danger/40")}
      footer={
        <>
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
            data-shortcut="⌘↵"
            title="Cmd or Ctrl + Enter"
            disabled={!canConfirm}
            loading={busy}
            onClick={() => onConfirm(phrase)}
          >
            Confirm
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        {target ? (
          <p className="text-sm" data-testid="confirm-dialog-v2-target">
            On <span className="font-semibold text-ink">{target.name}</span>{" "}
            <span className={cn("rounded px-1.5 py-0.5 text-xs font-medium", target.environment === "Live" ? "bg-danger-subtle text-danger" : "bg-surface-muted text-muted")}>{target.certain ? target.environment : `Probably ${target.environment === "Live" ? "live" : "a test copy"}`}</span>
          </p>
        ) : null}
        {target ? (() => {
          const st = stakesFor({ danger, environment: target.environment, certain: target.certain });
          return <p className={cn("text-sm", st === "high" ? "font-medium text-ink" : "text-muted")} data-testid="confirm-dialog-v2-stakes" data-stakes={st}>{stakesLine(st)}</p>;
        })() : null}
        <p className="text-sm text-muted">{warning}</p>

        {blastRadius && blastRadius.length > 0 ? (
          <div
            className="rounded-md border border-border-subtle bg-surface px-3 py-2"
            data-testid="confirm-dialog-v2-blast-radius"
          >
            <p className="text-xs font-medium uppercase tracking-wide text-muted">Blast radius</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-4 text-sm text-ink">
              {blastRadius.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        ) : null}

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
            ref={inputRef}
            data-testid="confirm-dialog-v2-input"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            disabled={busy}
            autoFocus
            className="mt-1 w-full rounded-md border border-border-subtle bg-surface px-3 py-2 text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
          />
        </label>
      </div>
    </DialogPanel>
  );
}
