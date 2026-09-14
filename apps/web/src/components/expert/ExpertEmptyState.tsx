"use client";

import { Button } from "@/components/ui/Button";
import { expertEmptyBody, expertEmptyTitle, expertHonestyLegend } from "@/lib/expert-journey";
import type { ExpertSuggestedPrompt } from "@/lib/api";

type ExpertEmptyStateProps = {
  prompts?: ExpertSuggestedPrompt[];
  onSelectPrompt: (question: string) => void;
  loadingPrompts?: boolean;
};

export function ExpertEmptyState({
  prompts = [],
  onSelectPrompt,
  loadingPrompts,
}: ExpertEmptyStateProps) {
  return (
    <div className="expert-empty" data-testid="expert-empty">
      <p className="expert-empty-title">{expertEmptyTitle()}</p>
      <p className="expert-empty-body">{expertEmptyBody()}</p>
      <ul className="expert-honesty-legend" data-testid="expert-honesty-legend">
        {expertHonestyLegend().map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      {loadingPrompts ? (
        <p className="mt-3 text-xs text-muted">Loading suggested prompts…</p>
      ) : null}
      {prompts.length > 0 ? (
        <div className="expert-prompt-row" data-testid="expert-suggested-prompts">
          {prompts.map((p) => (
            <Button
              key={p.id}
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => onSelectPrompt(p.question)}
            >
              {p.label}
            </Button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
