"use client";

import type { PreviewStatusBar } from "@/lib/draft-form-preview";

type OdooStatusBarProps = {
  statusbar: PreviewStatusBar;
};

export function OdooStatusBar({ statusbar }: OdooStatusBarProps) {
  const active = statusbar.activeStage || statusbar.stages[0];
  return (
    <div className="odoo-statusbar" data-testid="odoo-statusbar">
      {statusbar.stages.map((stage) => (
        <span
          key={stage}
          className={`odoo-statusbar-stage ${stage === active ? "is-active" : ""}`}
        >
          {stage.replaceAll("_", " ")}
        </span>
      ))}
    </div>
  );
}
