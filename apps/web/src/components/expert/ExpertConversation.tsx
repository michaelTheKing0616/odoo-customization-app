"use client";

import { useEffect, useRef } from "react";
import { StageProgress } from "@/components/progress/StageProgress";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { usePrefersReducedMotion } from "@/components/ui/motion/usePrefersReducedMotion";
import type { ExpertConversationState } from "@/lib/use-expert-conversation";
import { ExpertComposer } from "./ExpertComposer";
import { ExpertContextBar } from "./ExpertContextBar";
import { ExpertThread } from "./ExpertThread";

type ExpertConversationProps = {
  state: ExpertConversationState;
};

/**
 * The one Expert conversation view. The drawer (`ExpertPanel`) and the /expert page
 * (`ExpertPanel variant="page"`) both render this, so they cannot drift apart.
 */
export function ExpertConversation({ state }: ExpertConversationProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const reduced = usePrefersReducedMotion();
  const turnCount = state.turns.length;

  // Scroll the thread itself, never the page. A fresh answer lands with its question
  // pinned near the top so a long reply is read from the start, not the end.
  const lastRole = state.turns[turnCount - 1]?.role;
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    let top = el.scrollHeight;
    if (lastRole === "assistant" && !state.busy && !state.error) {
      const questions = el.querySelectorAll<HTMLElement>(".expert-turn-user");
      const question = questions[questions.length - 1];
      if (question) {
        const offset = question.getBoundingClientRect().top - el.getBoundingClientRect().top;
        top = Math.max(0, el.scrollTop + offset - 16);
      }
    }
    if (typeof el.scrollTo === "function") {
      el.scrollTo({ top, behavior: reduced ? "auto" : "smooth" });
    } else {
      el.scrollTop = top;
    }
  }, [turnCount, lastRole, state.busy, state.error, reduced]);

  return (
    <div
      className="expert-conversation"
      data-surface={state.surface}
      data-testid="expert-conversation"
    >
      <ExpertContextBar
        contextLabel={state.contextLabel}
        contextEnabled={state.contextEnabled}
        onToggleContext={state.toggleContext}
        canClear={turnCount > 0}
        busy={state.busy}
        onClear={state.requestClear}
      />
      {state.busy ? (
        <StageProgress
          runId={state.progressRunId}
          active
          className="stage-progress expert-progress"
          fallbackLabel="Retrieving sources…"
          onStop={state.stop}
        />
      ) : null}
      <ExpertThread
        turns={state.turns}
        busy={false}
        error={state.error}
        canRetry={state.canRetry}
        onRetry={state.retryLast}
        onFresh={state.freshLast}
        onDismissError={state.dismissError}
        prompts={state.prompts}
        loadingPrompts={state.loadingPrompts}
        onSelectPrompt={state.askStarter}
        showHonestyLegend={state.surface === "drawer"}
        connectionId={state.connectionId}
        chatterModel={state.uiContext.model}
        chatterResId={state.uiContext.resId}
        scrollRef={scrollRef}
      />
      <ExpertComposer
        value={state.input}
        onChange={state.setInput}
        errorPaste={state.errorPaste}
        onErrorPasteChange={state.setErrorPaste}
        errorInMainInput={state.errorInMainInput}
        busy={state.busy}
        onSubmit={state.submit}
        focusNonce={state.focusNonce}
        autoFocus={state.surface === "page"}
      />
    </div>
  );
}

export function ExpertClearDialog({ state }: ExpertConversationProps) {
  return (
    <ConfirmDialogV2
      open={state.clearConfirmOpen}
      riskLevel="standard"
      title="Start a new Expert thread?"
      warning="This clears the current conversation in this browser."
      risks={[
        "Prior turns are removed from local thread storage",
        "You can still ask a new question afterward",
      ]}
      phrase="I understand the risks"
      busy={state.busy}
      onCancel={() => state.setClearConfirmOpen(false)}
      onConfirm={() => state.confirmClear()}
    />
  );
}
