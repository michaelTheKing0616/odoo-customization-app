"use client";

import { useEffect, useRef } from "react";
import { STUDIO_STARTER_CHIPS } from "@/lib/studio-session";
import { STUDIO_STARTER_CHIP_LABELS } from "@/lib/studio-journey";
import { SuggestionChip } from "./SuggestionChip";
import { StudioBusyLabel } from "./StudioBusyLabel";

/** Shortest brief the Start button accepts (unchanged contract). */
const MIN_BRIEF_CHARS = 10;

type StudioBriefScreenProps = {
  prompt: string;
  busy: boolean;
  onPromptChange: (value: string) => void;
  onStart: () => void;
  /** Enrich Must-do with Flash. On: Flash AST fill. Off: deterministic floor only. */
  flashAstEnrich?: boolean;
  onFlashAstEnrichChange?: (value: boolean) => void;
  flashAstEnrichHelp?: string;
};

function disableReason(prompt: string, busy: boolean): string {
  if (busy) return "Starting the preview…";
  if (prompt.trim().length < MIN_BRIEF_CHARS) {
    return "A sentence or two is enough to start.";
  }
  return "Enter to continue. Shift + Enter adds a new line.";
}

export function StudioBriefScreen({
  prompt,
  busy,
  onPromptChange,
  onStart,
  flashAstEnrich = false,
  onFlashAstEnrichChange,
  flashAstEnrichHelp,
}: StudioBriefScreenProps) {
  const tooShort = prompt.trim().length < MIN_BRIEF_CHARS;
  const canStart = !busy && !tooShort;
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(Math.max(el.scrollHeight, 120), 280)}px`;
  }, [prompt]);

  function tryStart() {
    if (!canStart) return;
    onStart();
  }

  return (
    <section
      className="studio-prompt-screen studio-prompt-screen--hero"
      data-testid="studio-brief"
      aria-labelledby="studio-brief-title"
    >
      <h2 id="studio-brief-title" className="studio-prompt-title">
        What should people do in Odoo?
      </h2>
      <p className="studio-prompt-subtitle" id="studio-brief-help">
        Describe it in everyday words. You&apos;ll see a form preview first, and nothing is
        installed until you say so.
      </p>
      <div className="studio-prompt-composer">
        <label htmlFor="studio-prompt" className="sr-only">
          Describe the change
        </label>
        <textarea
          id="studio-prompt"
          ref={textareaRef}
          rows={3}
          value={prompt}
          onChange={(e) => onPromptChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key !== "Enter") return;
            if (e.shiftKey) return;
            // Enter alone, or Ctrl/⌘ + Enter, submits when ready (ChatGPT-class).
            if (!canStart) return;
            e.preventDefault();
            tryStart();
          }}
          aria-describedby="studio-brief-help studio-brief-status"
          placeholder="On vendor bills, add a Vendor TIN field that accountants fill in before confirming."
          className="input textarea studio-prompt-textarea"
        />
        <div className="studio-chip-row studio-prompt-starters" aria-label="Start from an example">
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
            title={flashAstEnrichHelp || undefined}
          >
            <input
              type="checkbox"
              checked={flashAstEnrich}
              disabled={busy}
              onChange={(e) => onFlashAstEnrichChange(e.target.checked)}
              data-testid="studio-flash-ast-enrich-input"
            />
            <span className="studio-flash-enrich-copy">
              <span className="studio-flash-enrich-label">Let AI add to the must-do list</span>
              <span className="studio-flash-enrich-hint">
                {flashAstEnrich
                  ? "AI can add steps from your wording. It never removes the ones read straight from your brief."
                  : "Off: only steps read straight from your brief."}
              </span>
            </span>
          </label>
        ) : null}
        <div className="studio-prompt-actions">
          <p className="studio-prompt-shortcut" id="studio-brief-status" aria-live="polite">
            {disableReason(prompt, busy)}
          </p>
          <button
            type="button"
            className="btn btn-primary studio-prompt-cta"
            disabled={!canStart}
            aria-describedby="studio-brief-status"
            onClick={tryStart}
          >
            {busy ? <StudioBusyLabel>Starting…</StudioBusyLabel> : "See a preview"}
          </button>
        </div>
      </div>
    </section>
  );
}
