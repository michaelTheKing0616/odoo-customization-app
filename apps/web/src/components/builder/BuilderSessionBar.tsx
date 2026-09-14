"use client";

import { useEffect, type ComponentProps } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { BuilderSessionState } from "@/lib/builderForm";

const STATE_COPY: Record<
  BuilderSessionState,
  { label: string; variant: ComponentProps<typeof Badge>["variant"]; hint: string }
> = {
  unsaved: {
    label: "Unsaved",
    variant: "warning",
    hint: "This draft stays local until you create it on Odoo. Existing snapshots are unchanged.",
  },
  saved: {
    label: "Saved",
    variant: "success",
    hint: "Last write landed on Odoo. Add a field, open View Designer, or start another model.",
  },
  draft: {
    label: "Draft",
    variant: "default",
    hint: "Name the model or field, then create it on this Odoo instance.",
  },
};

type BuilderSessionBarProps = {
  sessionState: BuilderSessionState;
  busy?: boolean;
  canDiscard?: boolean;
  submitLabel: string;
  onDiscard: () => void;
};

export function BuilderSessionBar({
  sessionState,
  busy,
  canDiscard,
  submitLabel,
  onDiscard,
}: BuilderSessionBarProps) {
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
      data-testid="builder-session-bar"
    >
      <span data-testid="builder-session-state">
        <Badge variant={copy.variant}>{copy.label}</Badge>
      </span>
      <p className="mr-auto max-w-xl text-xs text-muted" data-testid="builder-session-hint">
        {copy.hint}
      </p>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={busy || !canDiscard}
        onClick={onDiscard}
        data-testid="builder-discard"
      >
        Discard
      </Button>
      <span className="text-xs text-muted" data-testid="builder-session-submit-hint">
        {submitLabel}
      </span>
    </div>
  );
}
