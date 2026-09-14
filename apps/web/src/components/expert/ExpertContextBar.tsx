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
      <div className="flex min-w-0 flex-1 items-center gap-2 text-xs">
        {contextLabel ? (
          <span className="truncate text-muted">
            Using context: <span className="font-medium text-ink">{contextLabel}</span>
          </span>
        ) : (
          <span className="truncate text-muted" data-testid="expert-session-hint">
            {expertSessionHint({ contextEnabled, contextLabel })}
          </span>
        )}
        <button
          type="button"
          className="shrink-0 text-accent hover:underline"
          onClick={onToggleContext}
          data-testid="expert-context-toggle"
        >
          {contextEnabled ? "Turn off" : "Turn on"}
        </button>
      </div>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={!canClear || busy}
        data-testid="expert-clear-history"
        onClick={onClear}
      >
        New thread
      </Button>
    </div>
  );
}
