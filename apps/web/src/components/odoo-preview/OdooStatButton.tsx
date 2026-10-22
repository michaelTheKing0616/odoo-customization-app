"use client";

import type { PreviewSmartButton } from "@/lib/draft-form-preview";
import { BoxIcon } from "./OdooIcons";

type OdooStatButtonProps = {
  button: PreviewSmartButton;
};

export function OdooStatButton({ button }: OdooStatButtonProps) {
  return (
    <div className="ofp-stat" data-testid={`odoo-stat-${button.id}`}>
      <BoxIcon className="ofp-icon ofp-stat-icon" />
      <span className="ofp-stat-info">
        <span className="ofp-stat-value">{button.count != null ? button.count : 0}</span>
        <span className="ofp-stat-text">{button.string}</span>
      </span>
    </div>
  );
}
