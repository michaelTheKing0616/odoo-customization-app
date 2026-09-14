"use client";

import { Badge } from "@/components/ui/Badge";
import { locatorKind } from "@/lib/xpathLocator";

export type OverlayHudProps = {
  fieldName: string | null;
  ttype?: string | null;
  xpath: string;
  matchCount?: number | null;
  hover?: string | null;
  loading?: boolean;
  loadError?: string | null;
};

const KIND_BADGE: Record<
  ReturnType<typeof locatorKind>,
  { label: string; variant: "success" | "warning" | "default" }
> = {
  named: { label: "Named", variant: "success" },
  positional: { label: "Positional", variant: "warning" },
  fragile: { label: "Fragile", variant: "warning" },
  unknown: { label: "No locator", variant: "default" },
};

export function OverlayHud({
  fieldName,
  ttype,
  xpath,
  matchCount,
  hover,
  loading,
  loadError,
}: OverlayHudProps) {
  const kind = locatorKind(xpath);
  const badge = KIND_BADGE[kind];

  if (loading) {
    return (
      <div
        className="rounded-md border border-border-subtle bg-surface-muted px-3 py-2"
        data-testid="overlay-hud"
      >
        <p className="text-sm text-muted" data-testid="overlay-selected">
          Loading parent view
        </p>
      </div>
    );
  }

  if (loadError) {
    return (
      <div
        className="rounded-md border border-danger/30 bg-danger-subtle px-3 py-2"
        data-testid="overlay-hud"
      >
        <p className="text-sm text-ink">Could not load the parent view</p>
        <p className="mt-1 text-xs text-muted" data-testid="overlay-selected">
          {loadError}
        </p>
      </div>
    );
  }

  if (!fieldName) {
    return (
      <div
        className="rounded-md border border-border-subtle bg-surface-muted px-3 py-2"
        data-testid="overlay-hud"
      >
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
          Selected field
        </p>
        <p className="mt-1 text-sm text-muted" data-testid="overlay-selected">
          {hover
            ? `Hover ${hover}. Click to inspect, or add a page or group without a selection.`
            : "Click a field in the preview, or add a page or group without a selection."}
        </p>
      </div>
    );
  }

  return (
    <div
      className="rounded-md border border-border-subtle bg-surface-raised px-3 py-2 shadow-subtle"
      data-testid="overlay-hud"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
            Selected field
          </p>
          <p className="mt-1 truncate font-mono text-sm text-ink" data-testid="overlay-selected">
            {fieldName}
          </p>
          <p className="mt-0.5 text-xs text-muted">
            {ttype || "unknown type"}
            {matchCount != null ? ` · ${matchCount} match${matchCount === 1 ? "" : "es"}` : ""}
          </p>
        </div>
        <span data-testid="overlay-locator-kind">
          <Badge variant={badge.variant}>{badge.label}</Badge>
        </span>
      </div>
    </div>
  );
}
