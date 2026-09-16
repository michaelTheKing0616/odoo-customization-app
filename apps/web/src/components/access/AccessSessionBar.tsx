"use client";

import {
  ComposerSessionBar,
  type ComposerSessionState,
} from "@/components/ui/ComposerSessionBar";

const HINTS: Record<ComposerSessionState, string> = {
  unsaved:
    "This grant stays local until you create it on Odoo. Existing snapshots are unchanged.",
  saved:
    "Last create wrote this grant to Odoo and took a snapshot. Start another, or open a row from the list.",
  draft: "Name the access line or record rule, pick a group, then grant permissions.",
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
