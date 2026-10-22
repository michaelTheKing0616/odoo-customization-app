"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { FrameMeta } from "@/components/frame/FrameMeta";

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
  /** Skip the page-padding bleed (standalone harnesses with no app layout padding). */
  flush?: boolean;
  testId?: string;
};

/**
 * Studio mental model (Webflow 3-pane, UI-S-12): basalt chrome on top and on
 * the right, the canvas desk in the middle. The chrome carries the app's
 * `.dark` token scope plus `.designer-chrome` (basalt/limestone), so every
 * token-driven child renders on dark without per-component forks.
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
  flush = false,
  testId = "designer-page",
}: DesignerStudioShellProps) {
  return (
    <div
      className={cn(
        "designer-studio-shell mb-0 flex min-h-[calc(100dvh-4.5rem)] flex-col bg-background",
        !flush && "-mx-4 -mt-4 md:-mx-6 md:-mt-6",
        className,
      )}
      data-testid={testId}
    >
      <header
        className="designer-chrome designer-studio-header dark shrink-0 px-4 md:px-5"
        data-testid="designer-studio-header"
      >
        <div className="designer-titlebar">
          <div className="min-w-0 flex-1 basis-56">
            <FrameMeta />
            <h1 className="designer-title">{title}</h1>
            {description ? (
              <p className="designer-subtitle" title={description}>
                {description}
              </p>
            ) : null}
          </div>
          <div className="min-w-0 max-w-full">{sessionBar}</div>
        </div>
        {toolbar ? <div className="designer-toolbar-row">{toolbar}</div> : null}
        {notices ? <div className="designer-notices space-y-2">{notices}</div> : null}
      </header>
      <div
        className="flex min-h-0 flex-1 flex-col lg:min-h-[36rem] lg:flex-row"
        data-testid="designer-studio-body"
      >
        <section
          className="designer-studio-canvas min-h-[28rem] min-w-0 flex-1 overflow-auto"
          data-testid="designer-studio-canvas"
          aria-label="Canvas"
        >
          {canvas}
        </section>
        <aside
          className="designer-chrome designer-studio-rail dark flex w-full shrink-0 flex-col overflow-auto border-t lg:sticky lg:top-0 lg:max-h-dvh lg:w-[22.5rem] lg:self-stretch lg:border-l lg:border-t-0"
          data-testid="designer-tools-rail"
          aria-label="Modification tools"
        >
          {rail}
        </aside>
      </div>
      {extras}
    </div>
  );
}
