"use client";

import type { ReactNode, RefObject } from "react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

export type DesignerCanvasMode = "live" | "structure";

type DesignerLiveCanvasProps = {
  mode: DesignerCanvasMode;
  onModeChange: (mode: DesignerCanvasMode) => void;
  liveUrl: string | null;
  iframeRef: RefObject<HTMLIFrameElement | null>;
  iframeKey: number;
  liveFailed?: boolean;
  onLiveError?: () => void;
  onLiveLoad?: () => void;
  onRefreshLive?: () => void;
  openInOdooUrl?: string | null;
  structural: ReactNode;
  overlaySlot?: ReactNode;
};

export function DesignerLiveCanvas({
  mode,
  onModeChange,
  liveUrl,
  iframeRef,
  iframeKey,
  liveFailed = false,
  onLiveError,
  onLiveLoad,
  onRefreshLive,
  openInOdooUrl,
  structural,
  overlaySlot,
}: DesignerLiveCanvasProps) {
  const liveAvailable = Boolean(liveUrl) && !liveFailed;
  const showLive = mode === "live" && liveAvailable;

  return (
    <div className="flex h-full min-h-[28rem] flex-col" data-testid="designer-live-canvas">
      <div className="flex flex-wrap items-center gap-2 border-b border-border-subtle bg-surface px-3 py-2">
        <div
          className="inline-flex rounded-md border border-border-subtle p-0.5"
          data-testid="designer-canvas-mode"
          role="group"
          aria-label="Canvas mode"
        >
          <button
            type="button"
            className={cn(
              "rounded px-2.5 py-1 text-xs font-medium",
              showLive ? "bg-accent text-on-accent" : "text-muted hover:text-ink",
            )}
            data-testid="designer-canvas-mode-live"
            disabled={!liveUrl}
            onClick={() => onModeChange("live")}
          >
            Live Odoo
          </button>
          <button
            type="button"
            className={cn(
              "rounded px-2.5 py-1 text-xs font-medium",
              !showLive ? "bg-accent text-on-accent" : "text-muted hover:text-ink",
            )}
            data-testid="designer-canvas-mode-structure"
            onClick={() => onModeChange("structure")}
          >
            Layout canvas
          </button>
        </div>
        {liveFailed ? (
          <p className="text-xs text-warning" data-testid="designer-live-fallback">
            Live preview could not load — showing the Odoo-style layout canvas.
          </p>
        ) : null}
        {!liveUrl ? (
          <p className="text-xs text-muted">Load a model to enable live preview.</p>
        ) : null}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {onRefreshLive && liveUrl ? (
            <Button type="button" size="sm" variant="ghost" onClick={onRefreshLive}>
              Refresh
            </Button>
          ) : null}
          {openInOdooUrl ? (
            <a
              href={openInOdooUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-8 items-center rounded-md border border-border-subtle px-3 text-sm text-ink hover:bg-surface-muted"
              data-testid="designer-open-in-odoo"
            >
              Open in Odoo
            </a>
          ) : null}
        </div>
      </div>

      <div className="relative min-h-0 flex-1 bg-[var(--odoo-canvas)]">
        {showLive ? (
          <iframe
            ref={iframeRef}
            key={iframeKey}
            title="Odoo live preview"
            src={liveUrl ?? undefined}
            className="h-full min-h-[32rem] w-full bg-surface"
            data-testid="designer-live-iframe"
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
            onError={() => onLiveError?.()}
            onLoad={() => onLiveLoad?.()}
          />
        ) : (
          <div className="h-full overflow-auto p-4 md:p-6" data-testid="designer-structural-canvas">
            {structural}
          </div>
        )}
        {overlaySlot && showLive ? (
          <div className="pointer-events-none absolute inset-x-0 top-0">{overlaySlot}</div>
        ) : null}
      </div>
    </div>
  );
}
