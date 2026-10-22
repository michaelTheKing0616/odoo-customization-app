"use client";

import type { PreviewStatusBar } from "@/lib/draft-form-preview";

type OdooStatusBarProps = {
  statusbar: PreviewStatusBar;
  /** Capitalize technical stage keys (form preview). Designer keeps raw keys. */
  humanize?: boolean;
};

export function stageLabel(stage: string, humanize = true): string {
  const text = stage.replaceAll("_", " ").trim();
  if (!humanize) return text;
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}

/** Odoo statusbar: arrow-shaped stage pills, current stage highlighted. */
export function OdooStatusBar({ statusbar, humanize = false }: OdooStatusBarProps) {
  const active = statusbar.activeStage || statusbar.stages[0];
  return (
    <div className="ofp-statusbar" data-testid="odoo-statusbar" role="list" aria-label="Stage">
      {statusbar.stages.map((stage) => {
        const current = stage === active;
        return (
          <span
            key={stage}
            role="listitem"
            aria-current={current ? "step" : undefined}
            className={`ofp-stage ${current ? "is-active" : ""}`}
          >
            {stageLabel(stage, humanize)}
          </span>
        );
      })}
    </div>
  );
}
