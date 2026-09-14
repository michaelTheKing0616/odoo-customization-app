"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Sheet } from "@/components/ui/Sheet";
import { useShell } from "@/context/ShellContext";
import { api } from "@/lib/api";
import { buildExpertAskPayload, formatExpertDiagnosePrompt, isExpertSetupStackQuestion } from "@/lib/expert-prompt";
import { EXPERT_HONESTY_LINE, formatExpertContextLabel } from "@/lib/expert-journey";
import {
  clearExpertThread,
  loadExpertThread,
  saveExpertThread,
  type ExpertTurn,
} from "@/lib/expert-thread-storage";
import { ExpertComposer } from "./ExpertComposer";
import { ExpertContextBar } from "./ExpertContextBar";
import { ExpertHeader } from "./ExpertHeader";
import { ExpertThread } from "./ExpertThread";
import "@/styles/studio-refinement.css";

type SendOptions = {
  errorText?: string;
  freshThread?: boolean;
};

export function ExpertPanel() {
  const {
    connectionId,
    expertOpen,
    setExpertOpen,
    uiContext,
    contextEnabled,
    setContextEnabled,
    expertPrefill,
    clearExpertPrefill,
  } = useShell();
  const [turns, setTurns] = useState<ExpertTurn[]>([]);
  const [input, setInput] = useState("");
  const [errorPaste, setErrorPaste] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoSubmitNonce, setAutoSubmitNonce] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const pendingAutoSubmit = useRef<SendOptions & { prompt: string } | null>(null);

  const promptsQuery = useQuery({
    queryKey: ["expert-suggested-prompts", uiContext.route, uiContext.model, uiContext.draftSummary],
    queryFn: () =>
      api.expertSuggestedPrompts({
        route: uiContext.route,
        model: uiContext.model,
        view_type: uiContext.viewType,
        draft_summary: uiContext.draftSummary,
      }),
    enabled: expertOpen,
    staleTime: 60_000,
  });

  useEffect(() => {
    setTurns(loadExpertThread(connectionId));
  }, [connectionId]);

  const contextLabel = useMemo(
    () => formatExpertContextLabel(uiContext, contextEnabled),
    [contextEnabled, uiContext],
  );

  const sendQuestion = useCallback(
    async (question: string, opts?: SendOptions) => {
      const { question: payloadQuestion, pastedError } = buildExpertAskPayload(
        question,
        opts?.errorText ?? errorPaste,
      );
      const q = payloadQuestion.trim();
      if (!q || busy) return;
      setBusy(true);
      setError(null);
      const priorTurns = opts?.freshThread || isExpertSetupStackQuestion(q) ? [] : turns;
      const conversation = priorTurns.map((t) => ({
        role: t.role,
        content: t.role === "assistant" ? t.response?.answer_markdown ?? t.content : t.content,
      }));
      const userTurn: ExpertTurn = { role: "user", content: q };
      setTurns((prev) => {
        const base = opts?.freshThread ? [] : prev;
        const next = [...base, userTurn];
        saveExpertThread(connectionId, next);
        return next;
      });
      setInput("");
      setErrorPaste("");
      try {
        const ui_context = contextEnabled
          ? {
              ...uiContext,
              ...(pastedError ? { pasted_error: pastedError } : {}),
            }
          : pastedError
            ? { pasted_error: pastedError }
            : undefined;
        const response = await api.expertAsk({
          question: q,
          connection_id: connectionId,
          ui_context,
          conversation,
        });
        setTurns((prev) => {
          const next: ExpertTurn[] = [
            ...prev,
            { role: "assistant", content: response.answer_markdown, response },
          ];
          saveExpertThread(connectionId, next);
          return next;
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Expert request failed");
      } finally {
        setBusy(false);
      }
    },
    [busy, connectionId, contextEnabled, errorPaste, turns, uiContext],
  );

  const clearHistory = useCallback(() => {
    if (turns.length === 0 || busy) return;
    if (!window.confirm("Start a new Expert thread? This clears the current conversation.")) return;
    setTurns([]);
    setError(null);
    setInput("");
    setErrorPaste("");
    clearExpertThread(connectionId);
  }, [busy, connectionId, turns.length]);

  useEffect(() => {
    if (!expertPrefill?.question && !expertPrefill?.seedResponse) return;
    const {
      question,
      errorText,
      autoSubmit,
      freshThread,
      seedResponse,
      seedQuestion,
    } = expertPrefill;
    const prompt = formatExpertDiagnosePrompt(question, errorText);
    setInput(prompt);
    setErrorPaste(errorText?.trim() ?? "");
    if (freshThread) {
      setTurns([]);
      saveExpertThread(connectionId, []);
    }
    if (seedResponse) {
      const userQ = seedQuestion?.trim() || question.trim() || "Explain this";
      const seeded: ExpertTurn[] = [
        { role: "user", content: userQ },
        {
          role: "assistant",
          content: seedResponse.answer_markdown,
          response: seedResponse,
        },
      ];
      setTurns(seeded);
      saveExpertThread(connectionId, seeded);
      setInput("");
      clearExpertPrefill();
      return;
    }
    if (autoSubmit && prompt.trim()) {
      pendingAutoSubmit.current = {
        prompt,
        errorText: errorText?.trim(),
        freshThread: Boolean(freshThread),
      };
      setAutoSubmitNonce((n) => n + 1);
    }
    clearExpertPrefill();
  }, [expertPrefill, clearExpertPrefill, connectionId]);

  useEffect(() => {
    if (!expertOpen || !pendingAutoSubmit.current || busy) return;
    const { prompt, errorText, freshThread } = pendingAutoSubmit.current;
    pendingAutoSubmit.current = null;
    void sendQuestion(prompt, { errorText, freshThread });
  }, [expertOpen, busy, autoSubmitNonce, sendQuestion]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, busy]);

  const errorInMainInput = /\nError log:\n/i.test(input);

  return (
    <Sheet
      open={expertOpen}
      onOpenChange={setExpertOpen}
      title="Odoo Expert"
      description={EXPERT_HONESTY_LINE}
      testId="expert-panel"
      className="studio-refinement expert-drawer max-w-xl"
      header={<ExpertHeader />}
    >
      <div className="flex min-h-0 flex-1 flex-col">
        <ExpertContextBar
          contextLabel={contextLabel}
          contextEnabled={contextEnabled}
          onToggleContext={() => setContextEnabled(!contextEnabled)}
          canClear={turns.length > 0}
          busy={busy}
          onClear={clearHistory}
        />
        <ExpertThread
          turns={turns}
          busy={busy}
          error={error}
          prompts={promptsQuery.data}
          loadingPrompts={promptsQuery.isLoading}
          onSelectPrompt={(question) => void sendQuestion(question, { freshThread: true })}
          connectionId={connectionId}
          chatterModel={uiContext.model}
          chatterResId={uiContext.resId}
          bottomRef={bottomRef}
        />
        <ExpertComposer
          value={input}
          onChange={setInput}
          errorPaste={errorPaste}
          onErrorPasteChange={setErrorPaste}
          errorInMainInput={errorInMainInput}
          busy={busy}
          onSubmit={() => void sendQuestion(input)}
        />
      </div>
    </Sheet>
  );
}
