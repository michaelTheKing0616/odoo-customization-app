"use client";

import { Button } from "@/components/ui/Button";

export type Phase = { kind: "edit" } | { kind: "preview" } | { kind: "applying" } | { kind: "error"; message: string };

/** Shared preview-then-Apply step: list exactly what will change, then one Apply. */
export function PreviewApply({ title, changes, phase, onBack, onApply, applyLabel: applyLabelIn }: {
  title: string;
  changes: string[];
  phase: Phase;
  onBack: () => void;
  onApply: () => void;
  applyLabel?: string;
}) {
  // 91: buttons carry the number: "Apply 3 changes".
  const applyLabel = applyLabelIn ?? `Apply ${changes.length} ${changes.length === 1 ? "change" : "changes"}`;
  return (
    <div className="space-y-3 rounded-md border border-border-subtle bg-surface-muted p-3" data-testid="preview-apply">
      <p className="text-ui-body font-medium text-ink">{title}</p>
      <ul className="list-disc space-y-0.5 pl-5 text-ui-body text-ink" data-testid="change-summary">
        {changes.map((c) => <li key={c}>{c}</li>)}
      </ul>
      <p className="text-ui-meta text-muted">Nothing changes in Odoo until you press {applyLabel}.</p>
      {phase.kind === "error" ? (
        <p role="alert" className="text-ui-meta text-status-critical-strong" data-testid="apply-error">
          {`That didn't work: ${phase.message} Nothing was half-applied that we know of; you can try again.`}
        </p>
      ) : null}
      <div className="flex gap-2">
        <Button variant="primary" size="sm" onClick={onApply} disabled={phase.kind === "applying"} data-testid="apply">
          {phase.kind === "applying" ? "Applying…" : applyLabel}
        </Button>
        <Button variant="ghost" size="sm" onClick={onBack} disabled={phase.kind === "applying"}>Back</Button>
      </div>
    </div>
  );
}

export function errorText(err: unknown): string {
  const t = err instanceof Error ? err.message : String(err ?? "");
  return t || "Odoo didn't accept the change.";
}
