"use client";

import type { ReactNode } from "react";

/** Right-rail property inspector shell for Designer (Odoo-familiar). */

export function PropsInspector({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <aside className="odoo-sheet p-3">
      <h3 className="text-sm font-semibold text-[var(--odoo-primary)]">{title}</h3>
      <div className="mt-2 space-y-2 text-sm">{children}</div>
    </aside>
  );
}
