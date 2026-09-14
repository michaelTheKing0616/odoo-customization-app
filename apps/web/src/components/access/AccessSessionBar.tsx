"use client";

import { useEffect, type ComponentProps } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { AccessSessionState } from "@/lib/accessForm";

const STATE_COPY: Record<
  AccessSessionState,
  { label: string; variant: ComponentProps<typeof Badge>["variant"]; hint: string }
> = {
  unsaved: {
    label: "Unsaved",
    variant: "warning",
    hint: "This grant stays local until you create it on Odoo. Existing snapshots are unchanged.",
  },
  saved: {
    label: "Saved",
    variant: "success",
    hint: "Last create wrote this grant to Odoo and took a snapshot. Start another, or open a row from the list.",
  },
  draft: {
    label: "Draft",
    variant: "default",
    hint: "Name the access line or record rule, pick a group, then grant permissions.",
  },
};

type AccessSessionBarProps = {
  sessionState: AccessSessionState;
  busy?: boolean;
  canDiscard?: boolean;
  submitLabel: string;
  onDiscard: () => void;
};

export function AccessSessionBar({
  sessionState,
  busy,
  canDiscard,
  submitLabel,
  onDiscard,
}: AccessSessionBarProps) {
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
      data-testid="access-session-bar"
    >
      <span data-testid="access-session-state">
        <Badge variant={copy.variant}>{copy.label}</Badge>
      </span>
      <p className="mr-auto max-w-xl text-xs text-muted" data-testid="access-session-hint">
        {copy.hint}
      </p>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={busy || !canDiscard}
        onClick={onDiscard}
        data-testid="access-discard"
      >
        Discard
      </Button>
      <span className="text-xs text-muted" data-testid="access-session-submit-hint">
        {submitLabel}
      </span>
    </div>
  );
}
