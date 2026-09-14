"use client";

import { useEffect, type ComponentProps } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { MenuSessionState } from "@/lib/menuForm";

const STATE_COPY: Record<
  MenuSessionState,
  { label: string; variant: ComponentProps<typeof Badge>["variant"]; hint: string }
> = {
  unsaved: {
    label: "Unsaved",
    variant: "warning",
    hint: "This menu stays local until you create it on Odoo. Existing snapshots are unchanged.",
  },
  saved: {
    label: "Saved",
    variant: "success",
    hint: "Last create wrote this menu to Odoo and took a snapshot. Start another, or open an item from the tree.",
  },
  draft: {
    label: "Draft",
    variant: "default",
    hint: "Name the menu, pick a parent, then bind a window action. Restrict visibility by group when this is an app tile.",
  },
};

type MenuSessionBarProps = {
  sessionState: MenuSessionState;
  busy?: boolean;
  canDiscard?: boolean;
  submitLabel: string;
  onDiscard: () => void;
};

export function MenuSessionBar({
  sessionState,
  busy,
  canDiscard,
  submitLabel,
  onDiscard,
}: MenuSessionBarProps) {
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
      data-testid="menus-session-bar"
    >
      <span data-testid="menus-session-state">
        <Badge variant={copy.variant}>{copy.label}</Badge>
      </span>
      <p className="mr-auto max-w-xl text-xs text-muted" data-testid="menus-session-hint">
        {copy.hint}
      </p>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={busy || !canDiscard}
        onClick={onDiscard}
        data-testid="menus-discard"
      >
        Discard
      </Button>
      <span className="text-xs text-muted" data-testid="menus-session-submit-hint">
        {submitLabel}
      </span>
    </div>
  );
}
