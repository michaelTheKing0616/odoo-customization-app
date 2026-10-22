"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useShell } from "@/context/ShellContext";
import { api } from "@/lib/api";
import {
  buildExpertAskPayload,
  expertPrefillPrompt,
  isExpertSetupStackQuestion,
} from "@/lib/expert-prompt";
import { formatExpertContextLabel } from "@/lib/expert-journey";
import {
  clearExpertThread,
  loadExpertThread,
  saveExpertThread,
  type ExpertTurn,
} from "@/lib/expert-thread-storage";
import { newProgressRunId } from "@/lib/progress/run-id";

/**
 * Where the Expert conversation is rendered. The drawer and the /expert page use the
 * same hook and the same view (`ExpertConversation`), so they cannot diverge (UI-S-25).
 */
export type ExpertSurface = "drawer" | "page";

type SendOptions = {
  /** Skip the AI cache for this question. */
  fresh?: boolean;
  errorText?: string;
  freshThread?: boolean;
  /** Prior turns to send as conversation history (retry passes the thread minus the failed turn). */
  history?: ExpertTurn[];
};

export type ExpertConversationState = ReturnType<typeof useExpertConversation>;

/** Last user question in the thread that never got an assistant answer (failed send). */
export function lastUnansweredQuestion(turns: ExpertTurn[]): string | null {
  const last = turns[turns.length - 1];
  return last?.role === "user" ? last.content : null;
}

export function useExpertConversation(surface: ExpertSurface) {
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
  /** The page surface is always on screen; the drawer only while open. */
  const surfaceOpen = surface === "page" || expertOpen;

  const [turns, setTurns] = useState<ExpertTurn[]>([]);
  const [input, setInput] = useState("");
  const [errorPaste, setErrorPaste] = useState("");
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [progressRunId, setProgressRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [autoSubmitNonce, setAutoSubmitNonce] = useState(0);
  const [focusNonce, setFocusNonce] = useState(0);
  const pendingAutoSubmit = useRef<(SendOptions & { prompt: string }) | null>(null);

  const promptsQuery = useQuery({
    queryKey: ["expert-suggested-prompts", uiContext.route, uiContext.model, uiContext.draftSummary],
    queryFn: () =>
      api.expertSuggestedPrompts({
        route: uiContext.route,
        model: uiContext.model,
        view_type: uiContext.viewType,
        draft_summary: uiContext.draftSummary,
      }),
    enabled: surfaceOpen,
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
      const runId = newProgressRunId("expert");
      setProgressRunId(runId);
      const priorTurns =
        opts?.freshThread || isExpertSetupStackQuestion(q) ? [] : (opts?.history ?? turns);
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
        const askBody = {
          question: q,
          connection_id: connectionId,
          ui_context,
          conversation,
          progress_run_id: runId,
        };
        const response = opts?.fresh
          ? await api.expertAsk(askBody, { fresh: true })
          : await api.expertAsk(askBody);
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
        setProgressRunId(null);
      }
    },
    [busy, connectionId, contextEnabled, errorPaste, turns, uiContext],
  );

  /** Re-send the question that failed. The unanswered user turn is replaced, not duplicated. */
  const retryLast = useCallback(() => {
    const question = lastUnansweredQuestion(turns);
    if (!question || busy) return;
    setTurns((prev) => {
      const next = prev.slice(0, -1);
      saveExpertThread(connectionId, next);
      return next;
    });
    void sendQuestion(question, { history: turns.slice(0, -1) });
  }, [busy, connectionId, sendQuestion, turns]);

  /** "Fresh answer": ask the last answered question again, skipping the AI cache. */
  const freshLast = useCallback(() => {
    if (busy || turns.length < 2) return;
    const last = turns[turns.length - 1];
    const prev = turns[turns.length - 2];
    if (last.role !== "assistant" || prev.role !== "user") return;
    const history = turns.slice(0, -2);
    setTurns(() => {
      saveExpertThread(connectionId, history);
      return history;
    });
    void sendQuestion(prev.content, { history, fresh: true });
  }, [busy, connectionId, sendQuestion, turns]);

  const dismissError = useCallback(() => setError(null), []);

  const requestClear = useCallback(() => {
    if (turns.length === 0 || busy) return;
    setClearConfirmOpen(true);
  }, [busy, turns.length]);

  const confirmClear = useCallback(() => {
    setTurns([]);
    setError(null);
    setInput("");
    setErrorPaste("");
    clearExpertThread(connectionId);
    setClearConfirmOpen(false);
  }, [connectionId]);

  useEffect(() => {
    if (!expertPrefill?.question && !expertPrefill?.seedResponse) return;
    const { question, errorText, autoSubmit, freshThread, seedResponse, seedQuestion } =
      expertPrefill;
    const prompt = expertPrefillPrompt(question, errorText);
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
        { role: "assistant", content: seedResponse.answer_markdown, response: seedResponse },
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
    if (!surfaceOpen || !pendingAutoSubmit.current || busy) return;
    const { prompt, errorText, freshThread } = pendingAutoSubmit.current;
    pendingAutoSubmit.current = null;
    void sendQuestion(prompt, { errorText, freshThread });
  }, [surfaceOpen, busy, autoSubmitNonce, sendQuestion]);

  /**
   * On the page surface, "Open Expert" (top bar, explain-this, diagnose) must not pop a second
   * copy in a drawer. Treat the request as "focus the composer" and release the drawer flag.
   */
  useEffect(() => {
    if (surface !== "page" || !expertOpen) return;
    setFocusNonce((n) => n + 1);
    setExpertOpen(false);
  }, [expertOpen, setExpertOpen, surface]);

  const stop = useCallback(() => setBusy(false), []);
  const errorInMainInput = /\nError log:\n/i.test(input);

  return {
    surface,
    connectionId,
    uiContext,
    turns,
    input,
    setInput,
    errorPaste,
    setErrorPaste,
    errorInMainInput,
    busy,
    stop,
    progressRunId,
    error,
    dismissError,
    canRetry: Boolean(error && lastUnansweredQuestion(turns)),
    retryLast,
    freshLast,
    prompts: promptsQuery.data,
    loadingPrompts: promptsQuery.isLoading && surfaceOpen,
    contextLabel,
    contextEnabled,
    toggleContext: () => setContextEnabled(!contextEnabled),
    sendQuestion,
    submit: () => void sendQuestion(input),
    askStarter: (question: string) => void sendQuestion(question, { freshThread: true }),
    clearConfirmOpen,
    setClearConfirmOpen,
    requestClear,
    confirmClear,
    focusNonce,
  };
}
