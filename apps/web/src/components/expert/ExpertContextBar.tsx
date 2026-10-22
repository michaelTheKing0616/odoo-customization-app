"use client";

import { Button } from "@/components/ui/Button";
import { expertSessionHint } from "@/lib/expert-journey";

type ExpertContextBarProps = {
  contextLabel: string | null;
  contextEnabled: boolean;
  onToggleContext: () => void;
  canClear: boolean;
  busy?: boolean;
  onClear: () => void;
};

export function ExpertContextBar({
  contextLabel,
  contextEnabled,
  onToggleContext,
  canClear,
  busy,
  onClear,
}: ExpertContextBarProps) {
  return (
    <div className="expert-context-bar" data-testid="expert-context-bar">
      <button
        type="button"
        role="switch"
        aria-checked={contextEnabled}
        className="expert-context-switch"
        onClick={onToggleContext}
        data-testid="expert-context-toggle"
      >
        <span className="expert-switch-track" aria-hidden>
          <span className="expert-switch-thumb" />
        </span>
        <span className="expert-context-switch-label">Page context</span>
      </button>
      <span
        className="expert-context-value"
        data-testid={contextLabel ? "expert-context-label" : "expert-session-hint"}
        title={contextLabel ?? undefined}
      >
        {contextLabel ? (
          <>
            <span className="sr-only">Using </span>
            {contextLabel}
          </>
        ) : (
          expertSessionHint({ contextEnabled, contextLabel })
        )}
      </span>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="expert-context-clear"
        disabled={!canClear || busy}
        data-testid="expert-clear-history"
        onClick={onClear}
      >
        New thread
      </Button>
    </div>
  );
}
