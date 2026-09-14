"use client";

import type { Ref } from "react";
import { Callout } from "@/components/ui/Callout";
import { IconExpert } from "@/components/ui/icons";
import { cn } from "@/lib/cn";
import { splitUserTurnForDisplay } from "@/lib/expert-journey";
import type { ExpertTurn } from "@/lib/expert-thread-storage";
import { ExpertAnswerCard } from "./ExpertAnswerCard";
import { ExpertEmptyState } from "./ExpertEmptyState";
import type { ExpertSuggestedPrompt } from "@/lib/api";

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
  prompts?: ExpertSuggestedPrompt[];
  loadingPrompts?: boolean;
  onSelectPrompt: (question: string) => void;
  connectionId: string;
  chatterModel?: string;
  chatterResId?: number;
  bottomRef?: Ref<HTMLDivElement>;
};

export function ExpertThread({
  turns,
  busy,
  error,
  prompts,
  loadingPrompts,
  onSelectPrompt,
  connectionId,
  chatterModel,
  chatterResId,
  bottomRef,
}: ExpertThreadProps) {
  return (
    <div className="expert-thread" data-testid="expert-thread">
      {turns.length === 0 ? (
        <ExpertEmptyState
          prompts={prompts}
          loadingPrompts={loadingPrompts}
          onSelectPrompt={onSelectPrompt}
        />
      ) : null}
      {turns.map((turn, idx) => {
        const userDisplay =
          turn.role === "user" ? splitUserTurnForDisplay(turn.content) : null;
        return (
          <div
            key={`${turn.role}-${idx}`}
            className={cn(
              "flex gap-2 text-sm",
              turn.role === "user" ? "justify-end" : "justify-start",
            )}
          >
            {turn.role === "assistant" ? (
              <div className="expert-avatar" aria-hidden>
                <IconExpert className="h-3.5 w-3.5" />
              </div>
            ) : null}
            <div
              className={cn(
                "max-w-[92%] px-3 py-2.5",
                turn.role === "user" ? "expert-bubble-user" : "expert-bubble-assistant",
              )}
            >
              {turn.role === "assistant" && turn.response ? (
                <ExpertAnswerCard
                  response={turn.response}
                  connectionId={connectionId}
                  chatterModel={chatterModel}
                  chatterResId={chatterResId}
                />
              ) : userDisplay ? (
                <div className="space-y-2">
                  <p className="whitespace-pre-wrap">{userDisplay.question}</p>
                  {userDisplay.errorLog ? (
                    <details className="expert-error-log">
                      <summary>Error log</summary>
                      <pre>{userDisplay.errorLog}</pre>
                    </details>
                  ) : null}
                </div>
              ) : (
                turn.content
              )}
            </div>
          </div>
        );
      })}
      {busy ? <ExpertTypingIndicator /> : null}
      {error ? (
        <Callout variant="danger" title="Expert unavailable" testId="expert-error">
          {error}
        </Callout>
      ) : null}
      <div ref={bottomRef} />
    </div>
  );
}
