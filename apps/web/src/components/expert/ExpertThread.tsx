"use client";

import type { Ref } from "react";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { IconExpert } from "@/components/ui/icons";
import { splitUserTurnForDisplay } from "@/lib/expert-journey";
import type { ExpertTurn } from "@/lib/expert-thread-storage";
import type { ExpertSuggestedPrompt } from "@/lib/api";
import { ExpertAnswerCard } from "./ExpertAnswerCard";
import { ExpertEmptyState } from "./ExpertEmptyState";

function ExpertTypingIndicator() {
  return (
    <div className="expert-typing" data-testid="expert-loading" role="status">
      <span className="expert-typing-dots" aria-hidden>
        <i />
        <i />
        <i />
      </span>
      <span>Retrieving sources…</span>
    </div>
  );
}

type ExpertThreadProps = {
  turns: ExpertTurn[];
  busy?: boolean;
  error?: string | null;
  canRetry?: boolean;
  onRetry?: () => void;
  /** Re-ask the last question without the AI cache. */
  onFresh?: () => void;
  onDismissError?: () => void;
  prompts?: ExpertSuggestedPrompt[];
  loadingPrompts?: boolean;
  onSelectPrompt: (question: string) => void;
  /** The drawer shows the honesty legend in its empty state; the page shows it in the side rail. */
  showHonestyLegend?: boolean;
  connectionId: string;
  chatterModel?: string;
  chatterResId?: number;
  /** The scroll container. The conversation scrolls this element, never the page. */
  scrollRef?: Ref<HTMLDivElement>;
  /** @deprecated kept for callers that still pass a sentinel; unused. */
  bottomRef?: Ref<HTMLDivElement>;
};

export function ExpertThread({
  turns,
  busy,
  error,
  canRetry,
  onRetry,
  onFresh,
  onDismissError,
  prompts,
  loadingPrompts,
  onSelectPrompt,
  showHonestyLegend = true,
  connectionId,
  chatterModel,
  chatterResId,
  scrollRef,
  bottomRef,
}: ExpertThreadProps) {
  return (
    <div
      ref={scrollRef}
      className="expert-thread"
      data-testid="expert-thread"
      role="log"
      aria-label="Expert conversation"
      aria-busy={busy || undefined}
    >
      {turns.length === 0 ? (
        <ExpertEmptyState
          prompts={prompts}
          loadingPrompts={loadingPrompts}
          onSelectPrompt={onSelectPrompt}
          showHonestyLegend={showHonestyLegend}
        />
      ) : null}
      {turns.map((turn, idx) => {
        if (turn.role === "user") {
          const userDisplay = splitUserTurnForDisplay(turn.content);
          return (
            <div key={`user-${idx}`} className="expert-turn expert-turn-user">
              <div className="expert-bubble-user">
                <p className="whitespace-pre-wrap">{userDisplay.question}</p>
                {userDisplay.errorLog ? (
                  <details className="expert-error-log">
                    <summary>Error log</summary>
                    <pre>{userDisplay.errorLog}</pre>
                  </details>
                ) : null}
              </div>
            </div>
          );
        }
        return (
          <div key={`assistant-${idx}`} className="expert-turn expert-turn-assistant">
            <div className="expert-avatar" aria-hidden>
              <IconExpert className="h-3.5 w-3.5" />
            </div>
            <div className="expert-bubble-assistant">
              {turn.response ? (
                <ExpertAnswerCard
                  response={turn.response}
                  connectionId={connectionId}
                  chatterModel={chatterModel}
                  chatterResId={chatterResId}
                />
              ) : (
                <p className="whitespace-pre-wrap">{turn.content}</p>
              )}
              {onFresh && !busy && idx === turns.length - 1 ? (
                <button
                  type="button"
                  className="expert-fresh"
                  onClick={onFresh}
                  data-testid="expert-fresh-answer"
                  title="Ask again without using a saved answer"
                >
                  Fresh answer
                </button>
              ) : null}
            </div>
          </div>
        );
      })}
      {busy ? <ExpertTypingIndicator /> : null}
      {error ? (
        <Callout
          variant="danger"
          title="Expert could not answer"
          testId="expert-error"
          className="expert-error-callout"
          actions={
            canRetry || onDismissError ? (
              <>
                {canRetry && onRetry ? (
                  <Button type="button" variant="secondary" size="sm" onClick={onRetry}>
                    Ask again
                  </Button>
                ) : null}
                {onDismissError ? (
                  <Button type="button" variant="ghost" size="sm" onClick={onDismissError}>
                    Dismiss
                  </Button>
                ) : null}
              </>
            ) : undefined
          }
        >
          <p className="expert-error-why">{error}</p>
          <p className="expert-error-next">
            Your question is kept in the thread. Ask again, or turn off page context if this page
            is large.
          </p>
        </Callout>
      ) : null}
      {bottomRef ? <div ref={bottomRef} aria-hidden /> : null}
    </div>
  );
}
