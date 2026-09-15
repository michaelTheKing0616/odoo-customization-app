"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

type DesignerStudioShellProps = {
  title?: string;
  description?: string;
  sessionBar: ReactNode;
  toolbar?: ReactNode;
  notices?: ReactNode;
  canvas: ReactNode;
  rail: ReactNode;
  extras?: ReactNode;
  className?: string;
  testId?: string;
};

/**
 * Studio mental model: session chrome on top, live/structural canvas in the
 * center, modification tools on the right. Full-bleed inside AppShell padding.
 */
export function DesignerStudioShell({
  title = "View designer",
  description,
  sessionBar,
  toolbar,
  notices,
  canvas,
  rail,
  extras,
  className,
  testId = "designer-page",
}: DesignerStudioShellProps) {
  return (
    <div
      className={cn(
        "designer-studio-shell -mx-4 -mt-4 mb-0 flex min-h-[calc(100vh-4.5rem)] flex-col bg-background md:-mx-6 md:-mt-6",
        className,
      )}
      data-testid={testId}
    >
      <header
        className="shrink-0 border-b border-border-subtle bg-surface-raised px-4 py-3 md:px-6"
        data-testid="designer-studio-header"
      >
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
              Customize
            </p>
            <h1 className="text-lg font-semibold tracking-tight text-ink">{title}</h1>
            {description ? (
              <p className="mt-0.5 max-w-3xl text-sm text-muted">{description}</p>
            ) : null}
          </div>
        </div>
        <div className="mt-3">{sessionBar}</div>
        {toolbar ? <div className="mt-3">{toolbar}</div> : null}
        {notices ? <div className="mt-3 space-y-2">{notices}</div> : null}
      </header>
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row" data-testid="designer-studio-body">
        <section
          className="designer-studio-canvas min-h-[28rem] min-w-0 flex-1 overflow-auto"
          data-testid="designer-studio-canvas"
        >
          {canvas}
        </section>
        <aside
          className="designer-studio-rail flex w-full shrink-0 flex-col overflow-auto border-t border-border-subtle bg-surface-raised lg:w-[22.5rem] lg:border-l lg:border-t-0"
          data-testid="designer-tools-rail"
        >
          {rail}
        </aside>
      </div>
      {extras}
    </div>
  );
}
