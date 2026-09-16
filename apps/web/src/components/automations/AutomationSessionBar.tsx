"use client";

import {
  ComposerSessionBar,
  type ComposerSessionState,
} from "@/components/ui/ComposerSessionBar";

const HINTS: Record<ComposerSessionState, string> = {
  unsaved:
    "This rule stays local until you create it on Odoo. Existing snapshots are unchanged.",
  saved:
    "Last create wrote this rule to Odoo and took a snapshot. Start another, or open a rule from the list.",
  draft: "Name the rule, pick a model and trigger, then choose a safe action.",
};

type AutomationSessionBarProps = {
  sessionState: ComposerSessionState;
  busy?: boolean;
  canDiscard?: boolean;
  submitLabel: string;
  onDiscard: () => void;
};

export function AutomationSessionBar({
  sessionState,
  busy,
  canDiscard,
  submitLabel,
  onDiscard,
}: AutomationSessionBarProps) {
  return (
    <ComposerSessionBar
      sessionState={sessionState}
      hint={HINTS[sessionState]}
      busy={busy}
      canDiscard={canDiscard}
      submitLabel={submitLabel}
      onDiscard={onDiscard}
      testIdPrefix="automations"
    />
  );
}
