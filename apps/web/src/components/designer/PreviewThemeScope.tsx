"use client";

import type { CSSProperties, ReactNode } from "react";

/** Scope Odoo-preview CSS vars — does not theme the app shell. */
export function PreviewThemeScope({
  previewVars,
  children,
  className,
}: {
  previewVars?: Record<string, string>;
  children: ReactNode;
  className?: string;
}) {
  const style = (previewVars ?? {}) as CSSProperties;
  return (
    <div className={className} style={style} data-testid="preview-theme-scope">
      {children}
    </div>
  );
}
