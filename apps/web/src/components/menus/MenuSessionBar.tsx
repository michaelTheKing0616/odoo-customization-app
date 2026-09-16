"use client";

import {
  ComposerSessionBar,
  type ComposerSessionState,
} from "@/components/ui/ComposerSessionBar";

const HINTS: Record<ComposerSessionState, string> = {
  unsaved:
    "This menu stays local until you create it on Odoo. Existing snapshots are unchanged.",
  saved:
    "Last create wrote this menu to Odoo and took a snapshot. Start another, or open an item from the tree.",
  draft:
    "Name the menu, pick a parent, then bind a window action. Restrict visibility by group when this is an app tile.",
};

type MenuSessionBarProps = {
  sessionState: ComposerSessionState;
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
  return (
    <ComposerSessionBar
      sessionState={sessionState}
      hint={HINTS[sessionState]}
      busy={busy}
      canDiscard={canDiscard}
      submitLabel={submitLabel}
      onDiscard={onDiscard}
      testIdPrefix="menus"
    />
  );
}
