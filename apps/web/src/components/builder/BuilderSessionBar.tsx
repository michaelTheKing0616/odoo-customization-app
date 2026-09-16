"use client";

import {
  ComposerSessionBar,
  type ComposerSessionState,
} from "@/components/ui/ComposerSessionBar";

const HINTS: Record<ComposerSessionState, string> = {
  unsaved:
    "This draft stays local until you create it on Odoo. Existing snapshots are unchanged.",
  saved:
    "Last write landed on Odoo. Add a field, open View Designer, or start another model.",
  draft: "Name the model or field, then create it on this Odoo instance.",
};

type BuilderSessionBarProps = {
  sessionState: ComposerSessionState;
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
  return (
    <ComposerSessionBar
      sessionState={sessionState}
      hint={HINTS[sessionState]}
      busy={busy}
      canDiscard={canDiscard}
      submitLabel={submitLabel}
      onDiscard={onDiscard}
      testIdPrefix="builder"
    />
  );
}
