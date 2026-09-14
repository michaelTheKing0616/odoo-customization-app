"use client";

import { useEffect, type ComponentProps } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { ModuleSpecSessionState } from "@/lib/modulespec-journey";

const STATE_COPY: Record<
  ModuleSpecSessionState,
  { label: string; variant: ComponentProps<typeof Badge>["variant"]; hint: string }
> = {
  unsaved: {
    label: "Unsaved",
    variant: "warning",
    hint: "Edits stay in this browser until you save the project or Generate UI. Completeness is not go-live.",
  },
  saved: {
    label: "Saved",
    variant: "success",
    hint: "Last save is the baseline. Validate, then Generate UI or export a zip. Promote stays human.",
  },
  draft: {
    label: "Draft",
    variant: "default",
    hint: "Load a handoff, import a zip, or add a model. Nothing writes to Odoo until Generate UI.",
  },
};

type ModuleSpecSessionBarProps = {
  sessionState: ModuleSpecSessionState;
  busy?: boolean;
  canDiscard?: boolean;
  submitLabel: string;
  onDiscard: () => void;
};

export function ModuleSpecSessionBar({
  sessionState,
  busy,
  canDiscard,
  submitLabel,
  onDiscard,
}: ModuleSpecSessionBarProps) {
  const copy = STATE_COPY[sessionState];

  useEffect(() => {
    if (sessionState !== "unsaved") return;
    function onBeforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault();
      event.returnValue = "";
    }
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [sessionState]);

  return (
    <div
      className="flex flex-wrap items-center gap-2 rounded-md border border-border-subtle bg-surface-raised px-3 py-2 shadow-subtle"
      data-testid="modulespec-session-bar"
    >
      <span data-testid="modulespec-session-state">
        <Badge variant={copy.variant}>{copy.label}</Badge>
      </span>
      <p className="mr-auto max-w-xl text-xs text-muted" data-testid="modulespec-session-hint">
        {copy.hint}
      </p>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={busy || !canDiscard}
        onClick={onDiscard}
        data-testid="modulespec-discard"
      >
        Discard
      </Button>
      <span className="text-xs text-muted" data-testid="modulespec-session-submit-hint">
        {submitLabel}
      </span>
    </div>
  );
}
