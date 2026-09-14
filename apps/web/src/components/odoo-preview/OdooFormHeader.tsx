"use client";

import type { PreviewFormView } from "@/lib/draft-form-preview";
import { OdooStatusBar } from "./OdooStatusBar";

type OdooFormHeaderProps = {
  title: string;
  statusbar?: PreviewFormView["statusbar"];
  headerButtons?: PreviewFormView["headerButtons"];
};

export function OdooFormHeader({ title, statusbar, headerButtons = [] }: OdooFormHeaderProps) {
  return (
    <div className="odoo-form-header flex flex-wrap items-center gap-2" data-testid="odoo-form-header">
      <span className="text-sm font-semibold text-[var(--odoo-primary)]">{title}</span>
      {statusbar ? <OdooStatusBar statusbar={statusbar} /> : null}
      <div className="ml-auto flex flex-wrap gap-1">
        {headerButtons.map((btn) => (
          <span
            key={btn.id}
            className={btn.variant === "primary" ? "odoo-btn-primary" : "odoo-btn-secondary"}
          >
            {btn.string}
          </span>
        ))}
      </div>
    </div>
  );
}
