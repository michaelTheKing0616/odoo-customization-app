"use client";

import type { ReactNode, RefObject } from "react";
import { ExternalLink } from "@/components/ui/icons";
import {
  canvasStateCopy,
  type DesignerCanvasState,
} from "@/components/designer/designerCanvasState";

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
  /** XML invalid / inherit conflict / preview stale, shown on the desk above the card. */
  canvasState?: DesignerCanvasState | null;
};

export function DesignerCanvasStateNotice({ state }: { state: DesignerCanvasState }) {
  const copy = canvasStateCopy(state);
  return (
    <div
      className="designer-canvas-state"
      data-testid="designer-canvas-state"
      data-state={state.kind}
      data-tone={copy.tone}
      role={copy.role}
    >
      <div className="designer-canvas-state-body">
        <p className="designer-canvas-state-title">{copy.title}</p>
        <p className="designer-canvas-state-text">{copy.text}</p>
        {copy.code ? (
          <p className="designer-canvas-state-code">
            {copy.codeLabel ? (
              <span className="designer-canvas-state-code-label">{copy.codeLabel}</span>
            ) : null}
            <code
              data-testid={
                state.kind === "inherit-conflict"
                  ? "designer-canvas-state-locator"
                  : "designer-canvas-state-code"
              }
            >
              {copy.code}
            </code>
          </p>
        ) : null}
      </div>
      {state.action ? (
        <button
          type="button"
          className="designer-canvas-state-action"
          onClick={state.action.onClick}
          data-testid="designer-canvas-state-action"
        >
          {state.action.label}
        </button>
      ) : null}
    </div>
  );
}

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
  canvasState = null,
}: DesignerLiveCanvasProps) {
  const liveAvailable = Boolean(liveUrl) && !liveFailed;
  const showLive = mode === "live" && liveAvailable;
  const liveStale = showLive && canvasState?.kind === "preview-stale";

  return (
    <div className="flex h-full min-h-[28rem] flex-col" data-testid="designer-live-canvas">
      <div className="designer-chrome designer-canvas-bar dark">
        <div
          className="designer-segmented"
          data-testid="designer-canvas-mode"
          role="group"
          aria-label="Canvas mode"
        >
          <button
            type="button"
            aria-pressed={showLive}
            data-testid="designer-canvas-mode-live"
            disabled={!liveUrl}
            onClick={() => onModeChange("live")}
          >
            Live Odoo
          </button>
          <button
            type="button"
            aria-pressed={!showLive}
            data-testid="designer-canvas-mode-structure"
            onClick={() => onModeChange("structure")}
          >
            Layout canvas
          </button>
        </div>
        {liveFailed ? (
          <p className="designer-bar-status is-warning" data-testid="designer-live-fallback">
            Live preview did not load, so the layout canvas is showing instead.
          </p>
        ) : null}
        {!liveUrl ? (
          <p className="designer-bar-status">Load a model to turn on the live preview.</p>
        ) : null}
        <div className="ml-auto flex flex-wrap items-center gap-1">
          {onRefreshLive && liveUrl ? (
            <button type="button" className="designer-bar-link" onClick={onRefreshLive}>
              Refresh
            </button>
          ) : null}
          {openInOdooUrl ? (
            <a
              href={openInOdooUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="designer-bar-link"
              data-testid="designer-open-in-odoo"
            >
              Open in Odoo
              <ExternalLink className="h-3.5 w-3.5" aria-hidden />
            </a>
          ) : null}
        </div>
      </div>

      <div className="designer-desk relative flex min-h-0 flex-1 flex-col">
        {canvasState ? <DesignerCanvasStateNotice state={canvasState} /> : null}
        {showLive ? (
          <div
            className={liveStale ? "designer-live-wrap is-stale" : "designer-live-wrap"}
            data-stale={liveStale ? "true" : undefined}
          >
            <iframe
              ref={iframeRef}
              key={iframeKey}
              title="Odoo live preview"
              src={liveUrl ?? undefined}
              className="designer-live-frame min-h-[32rem] w-full flex-1 rounded-[10px] border border-[var(--dz-paper-edge)] bg-surface shadow-[var(--dz-paper-lift)]"
              data-testid="designer-live-iframe"
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
              onError={() => onLiveError?.()}
              onLoad={() => onLiveLoad?.()}
            />
            {liveStale ? (
              <span className="designer-live-stale-tag" data-testid="designer-live-stale-tag">
                Last saved version
              </span>
            ) : null}
            {overlaySlot ? (
              <div className="pointer-events-none absolute inset-x-0 top-0">{overlaySlot}</div>
            ) : null}
          </div>
        ) : (
          <div className="designer-desk-inner w-full min-w-0" data-testid="designer-structural-canvas">
            {structural}
          </div>
        )}
      </div>
    </div>
  );
}
