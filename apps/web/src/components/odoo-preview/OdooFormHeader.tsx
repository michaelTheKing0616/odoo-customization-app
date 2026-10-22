"use client";

import type { PreviewFormView } from "@/lib/draft-form-preview";
import { OdooStatusBar } from "./OdooStatusBar";

type OdooFormHeaderProps = {
  title: string;
  statusbar?: PreviewFormView["statusbar"];
  headerButtons?: PreviewFormView["headerButtons"];
  humanizeStages?: boolean;
};

/** Odoo form header: action buttons left, statusbar right. */
export function OdooFormHeader({
  title,
  statusbar,
  headerButtons = [],
  humanizeStages = false,
}: OdooFormHeaderProps) {
  if (!statusbar && headerButtons.length === 0) return null;
  return (
    <div className="ofp-header" data-testid="odoo-form-header" aria-label={`${title} actions`}>
      <div className="ofp-header-buttons">
        {headerButtons.map((btn) => (
          <span
            key={btn.id}
            className={`ofp-btn ${btn.variant === "primary" ? "ofp-btn-primary" : "ofp-btn-secondary"}`}
          >
            {btn.string}
          </span>
        ))}
      </div>
      {statusbar ? <OdooStatusBar statusbar={statusbar} humanize={humanizeStages} /> : null}
    </div>
  );
}
