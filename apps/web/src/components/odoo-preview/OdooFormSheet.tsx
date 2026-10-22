"use client";

import type { ReactNode } from "react";

type OdooFormSheetProps = {
  children: ReactNode;
};

/** White sheet on the grey form backdrop (Odoo o_form_sheet_bg / o_form_sheet). */
export function OdooFormSheet({ children }: OdooFormSheetProps) {
  return (
    <div className="ofp-sheet-bg">
      <div className="ofp-sheet" data-testid="odoo-form-sheet">
        {children}
      </div>
    </div>
  );
}
