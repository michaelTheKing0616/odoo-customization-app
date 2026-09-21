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
  /** Enrich Must-do with Flash — on = Flash AST fill; off = det floor only */
  flashAstEnrich?: boolean;
  onFlashAstEnrichChange?: (value: boolean) => void;
  flashAstEnrichHelp?: string;
};

export function StudioBriefScreen({
  prompt,
  busy,
  onPromptChange,
  onStart,
  flashAstEnrich = false,
  onFlashAstEnrichChange,
  flashAstEnrichHelp,
}: StudioBriefScreenProps) {
  return (
    <div className="studio-prompt-screen studio-prompt-screen--hero" data-testid="studio-brief">
      <p className="studio-prompt-kicker">App Studio</p>
      <h2 className="studio-prompt-title">What should people do in Odoo?</h2>
      <p className="studio-prompt-subtitle">
        Describe it in everyday words. You&apos;ll see a form preview first — nothing is
        installed until you say so.
      </p>
      <div className="studio-prompt-composer">
        <Textarea
          id="studio-prompt"
          rows={4}
          value={prompt}
          onChange={(e) => onPromptChange(e.target.value)}
          placeholder="On vendor bills, add a Vendor TIN field that accountants fill in before confirming."
          className="resize-none text-left studio-prompt-textarea"
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
        {onFlashAstEnrichChange ? (
          <label
            className="studio-flash-enrich-toggle"
            data-testid="studio-flash-ast-enrich-toggle"
            title={
              flashAstEnrichHelp ||
              "On: optional Flash AST fill (same path as AI_INTENT_LLM). Off: deterministic floor only."
            }
          >
            <input
              type="checkbox"
              checked={flashAstEnrich}
              disabled={busy}
              onChange={(e) => onFlashAstEnrichChange(e.target.checked)}
              data-testid="studio-flash-ast-enrich-input"
            />
            <span>
              <strong>Enrich Must-do with Flash</strong>
              <span className="studio-flash-enrich-hint">
                {flashAstEnrich
                  ? " — Flash may fill free prose into Must-do (never shrinks the floor)."
                  : " — off = deterministic floor only."}
              </span>
            </span>
          </label>
        ) : null}
        <button
          type="button"
          className="btn btn-brand studio-prompt-cta"
          disabled={busy || prompt.trim().length < 10}
          onClick={onStart}
        >
          {busy ? <StudioBusyLabel>Starting…</StudioBusyLabel> : "See a preview"}
        </button>
      </div>
    </div>
  );
}
