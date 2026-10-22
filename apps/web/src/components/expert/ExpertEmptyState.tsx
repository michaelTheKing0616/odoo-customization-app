"use client";

import { useId } from "react";
import {
  EXPERT_STARTER_PROMPTS,
  expertEmptyBody,
  expertEmptyTitle,
  expertHonestyLegend,
} from "@/lib/expert-journey";
import type { ExpertSuggestedPrompt } from "@/lib/api";

type ExpertEmptyStateProps = {
  prompts?: ExpertSuggestedPrompt[];
  onSelectPrompt: (question: string) => void;
  loadingPrompts?: boolean;
  showHonestyLegend?: boolean;
};

/** Server prompts when the API has them; the curated starters otherwise, so the empty state always has a next step. */
export function resolveExpertStarters(
  prompts: ExpertSuggestedPrompt[] | undefined,
): ReadonlyArray<{ id: string; label: string; question: string }> {
  const fromApi = (prompts ?? []).filter((p) => p.label?.trim() && p.question?.trim());
  return (fromApi.length > 0 ? fromApi : EXPERT_STARTER_PROMPTS).slice(0, 4);
}

function StarterRow({
  label,
  question,
  onSelect,
}: {
  label: string;
  question: string;
  onSelect: () => void;
}) {
  const descId = useId();
  return (
    <li>
      <button
        type="button"
        className="expert-starter"
        aria-label={label}
        aria-describedby={descId}
        onClick={onSelect}
      >
        <span className="expert-starter-label">{label}</span>
        <span className="expert-starter-question" id={descId}>
          {question}
        </span>
      </button>
    </li>
  );
}

export function ExpertEmptyState({
  prompts,
  onSelectPrompt,
  loadingPrompts,
  showHonestyLegend = true,
}: ExpertEmptyStateProps) {
  const starters = resolveExpertStarters(prompts);
  return (
    <div className="expert-empty" data-testid="expert-empty">
      <h2 className="expert-empty-title">{expertEmptyTitle()}</h2>
      <p className="expert-empty-body">{expertEmptyBody()}</p>
      {loadingPrompts ? (
        <ul className="expert-starter-list" aria-hidden data-testid="expert-prompts-loading">
          {[0, 1, 2].map((i) => (
            <li key={i} className="expert-starter-skeleton" />
          ))}
        </ul>
      ) : (
        <ul className="expert-starter-list" data-testid="expert-suggested-prompts" aria-label="Try one of these">
          {starters.map((p) => (
            <StarterRow
              key={p.id}
              label={p.label}
              question={p.question}
              onSelect={() => onSelectPrompt(p.question)}
            />
          ))}
        </ul>
      )}
      {showHonestyLegend ? (
        <ul className="expert-honesty-legend" data-testid="expert-honesty-legend">
          {expertHonestyLegend().map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
