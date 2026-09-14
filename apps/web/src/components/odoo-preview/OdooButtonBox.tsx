"use client";

import type { PreviewSmartButton } from "@/lib/draft-form-preview";
import { OdooStatButton } from "./OdooStatButton";

type OdooButtonBoxProps = {
  buttons: PreviewSmartButton[];
};

export function OdooButtonBox({ buttons }: OdooButtonBoxProps) {
  if (buttons.length === 0) return null;
  return (
    <div className="odoo-button-box" data-testid="odoo-button-box">
      {buttons.map((button) => (
        <OdooStatButton key={button.id} button={button} />
      ))}
    </div>
  );
}
