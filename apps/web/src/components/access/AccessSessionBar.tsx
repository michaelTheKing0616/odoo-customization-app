"use client";

import {
  ComposerSessionBar,
  type ComposerSessionState,
} from "@/components/ui/ComposerSessionBar";

const HINTS: Record<ComposerSessionState, string> = {
  unsaved:
    "This right stays local until you save it to Odoo. Existing snapshots are unchanged.",
  saved:
    "Saved to Odoo after a snapshot. Start another, or open a line from the list.",
  draft: "Name it, pick a group, then tick the operations it may run.",
};

type AccessSessionBarProps = {
  sessionState: ComposerSessionState;
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
  return (
    <ComposerSessionBar
      sessionState={sessionState}
      hint={HINTS[sessionState]}
      busy={busy}
      canDiscard={canDiscard}
      submitLabel={submitLabel}
      onDiscard={onDiscard}
      testIdPrefix="access"
    />
  );
}
