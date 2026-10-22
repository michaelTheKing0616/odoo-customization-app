"use client";

import type { ReactNode } from "react";

/**
 * Right-rail property inspector shell for Designer (Odoo-familiar).
 * UI-S-12: renders inside the basalt rail; the drawer-in is the one animated
 * surface in the designer (≤300ms, reduced motion fades only).
 */

export function PropsInspector({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="designer-drawer-in" data-testid="designer-props-inspector">
      <h3 className="designer-props-inspector-title">{title}</h3>
      <div className="mt-3 space-y-3 text-sm">{children}</div>
    </section>
  );
}
