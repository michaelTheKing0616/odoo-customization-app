"use client";

import { useEffect, type ComponentProps } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

export type ComposerSessionState = "draft" | "unsaved" | "saved";

const STATE_BADGE: Record<
  ComposerSessionState,
  { label: string; variant: ComponentProps<typeof Badge>["variant"] }
> = {
  unsaved: { label: "Unsaved", variant: "warning" },
  saved: { label: "Saved", variant: "success" },
  draft: { label: "Draft", variant: "default" },
};

export type ComposerSessionBarProps = {
  sessionState: ComposerSessionState;
  hint: string;
  busy?: boolean;
  canDiscard?: boolean;
  submitLabel: string;
  onDiscard: () => void;
  /** Prefix for data-testid roots, e.g. "menus" → menus-session-bar */
  testIdPrefix?: string;
  className?: string;
};

export function ComposerSessionBar({
  sessionState,
  hint,
  busy,
  canDiscard,
  submitLabel,
  onDiscard,
  testIdPrefix = "composer",
  className,
}: ComposerSessionBarProps) {
  const badge = STATE_BADGE[sessionState];

  useEffect(() => {
    if (sessionState !== "unsaved") return;
    function onBeforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault();
      event.returnValue = "";
    }
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [sessionState]);

  const shell =
    className ??
    "sticky bottom-0 z-10 flex flex-wrap items-center gap-2 rounded-md border border-border-subtle bg-surface-raised px-3 py-2 shadow-subtle";

  return (
    <div className={shell} data-testid={`${testIdPrefix}-session-bar`}>
      <span data-testid={`${testIdPrefix}-session-state`}>
        <Badge variant={badge.variant}>{badge.label}</Badge>
      </span>
      <p
        className="mr-auto max-w-xl text-ui-meta text-muted"
        data-testid={`${testIdPrefix}-session-hint`}
      >
        {hint}
      </p>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={busy || !canDiscard}
        onClick={onDiscard}
        data-testid={`${testIdPrefix}-discard`}
      >
        Discard
      </Button>
      <span
        className="text-ui-meta text-muted"
        data-testid={`${testIdPrefix}-session-submit-hint`}
      >
        {submitLabel}
      </span>
    </div>
  );
}
