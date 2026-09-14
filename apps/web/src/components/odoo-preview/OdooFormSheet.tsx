"use client";

import type { ReactNode } from "react";

type OdooFormSheetProps = {
  children: ReactNode;
};

export function OdooFormSheet({ children }: OdooFormSheetProps) {
  return (
    <div className="odoo-form-workspace">
      <div className="odoo-form-sheet" data-testid="odoo-form-sheet">
        {children}
      </div>
    </div>
  );
}
