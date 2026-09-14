"use client";

import { Textarea } from "@/components/ui/Textarea";
import { STUDIO_STARTER_CHIPS } from "@/lib/studio-session";
import { STUDIO_STARTER_CHIP_LABELS } from "@/lib/studio-journey";
import { SuggestionChip } from "./SuggestionChip";
import { StudioBusyLabel } from "./StudioBusyLabel";

type StudioBriefScreenProps = {
  prompt: string;
  busy: boolean;
  onPromptChange: (value: string) => void;
  onStart: () => void;
};

export function StudioBriefScreen({
  prompt,
  busy,
  onPromptChange,
  onStart,
}: StudioBriefScreenProps) {
  return (
    <div className="studio-prompt-screen" data-testid="studio-brief">
      <h2 className="studio-prompt-title">What should people do in Odoo?</h2>
      <p className="studio-prompt-subtitle">
        Describe it in everyday words. You&apos;ll see a form preview first — nothing is
        installed until you say so.
      </p>
      <Textarea
        id="studio-prompt"
        rows={3}
        value={prompt}
        onChange={(e) => onPromptChange(e.target.value)}
        placeholder="On vendor bills, add a Vendor TIN field that accountants fill in before confirming."
        className="resize-none text-left"
      />
      <div className="studio-chip-row">
        {STUDIO_STARTER_CHIPS.map((chip) => (
          <SuggestionChip
            key={chip}
            label={STUDIO_STARTER_CHIP_LABELS[chip] || chip}
            onClick={() => onPromptChange(chip)}
          />
        ))}
      </div>
      <button
        type="button"
        className="btn btn-brand"
        disabled={busy || prompt.trim().length < 10}
        onClick={onStart}
      >
        {busy ? <StudioBusyLabel>Starting…</StudioBusyLabel> : "See a preview"}
      </button>
    </div>
  );
}
