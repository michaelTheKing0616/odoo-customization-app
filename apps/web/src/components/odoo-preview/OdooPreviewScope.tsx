"use client";

import type { ReactNode } from "react";
import { PreviewThemeScope } from "@/components/designer/PreviewThemeScope";

type OdooPreviewScopeProps = {
  children: ReactNode;
  className?: string;
  showBanner?: boolean;
  previewVars?: Record<string, string>;
};

export function OdooPreviewScope({
  children,
  className,
  showBanner = true,
  previewVars,
}: OdooPreviewScopeProps) {
  return (
    <PreviewThemeScope
      className={className ?? "odoo-shell rounded-md"}
      previewVars={previewVars}
    >
      {showBanner ? (
        <p className="odoo-preview-banner" data-testid="odoo-preview-banner">
          Structural preview — Open in Odoo for authoritative layout.
        </p>
      ) : null}
      {children}
    </PreviewThemeScope>
  );
}
