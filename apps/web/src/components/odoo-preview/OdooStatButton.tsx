"use client";

import type { PreviewSmartButton } from "@/lib/draft-form-preview";

type OdooStatButtonProps = {
  button: PreviewSmartButton;
};

export function OdooStatButton({ button }: OdooStatButtonProps) {
  return (
    <div className="odoo-stat-button" data-testid={`odoo-stat-${button.id}`}>
      {button.count != null ? (
        <span className="odoo-stat-value">{button.count}</span>
      ) : (
        <span className="odoo-stat-value">—</span>
      )}
      <span className="odoo-stat-text">{button.string}</span>
    </div>
  );
}
