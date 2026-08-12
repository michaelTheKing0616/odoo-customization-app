"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Markdown from "react-markdown";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Sheet } from "@/components/ui/Sheet";
import { ExternalLink } from "@/components/ui/icons";
import { Tooltip } from "@/components/ui/Tooltip";
import { useShell } from "@/context/ShellContext";
import { api, type ExpertAskResponse, type ExpertCitation } from "@/lib/api";
import { buildExpertAskPayload, formatExpertDiagnosePrompt } from "@/lib/expert-prompt";
import { cn } from "@/lib/cn";

type Turn = { role: "user" | "assistant"; content: string; response?: ExpertAskResponse };

type SendOptions = {
  errorText?: string;
  freshThread?: boolean;
};

function storageKey(connectionId: string) {
  return `expert-thread-${connectionId}`;
}

function loadThread(connectionId: string): Turn[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = sessionStorage.getItem(storageKey(connectionId));
    return raw ? (JSON.parse(raw) as Turn[]) : [];
  } catch {
    return [];
  }
}

function saveThread(connectionId: string, turns: Turn[]) {
  sessionStorage.setItem(storageKey(connectionId), JSON.stringify(turns));
}

function clearThread(connectionId: string) {
  sessionStorage.removeItem(storageKey(connectionId));
}

function CitationChip({ citation, index }: { citation: ExpertCitation; index?: number }) {
  const label = index ?? citation.source_index;
  return (
    <Tooltip
      label={`${citation.source} · ${citation.version} — ${citation.breadcrumb}`}
    >
      <sup className="cursor-help rounded bg-accent-subtle px-1 text-[10px] font-medium text-accent">
        [{label}]
      </sup>
    </Tooltip>
  );
}

/** Turn inline [n] markers into markdown links the custom anchor renderer converts to chips. */
function linkifyCitationMarkers(markdown: string): string {
  return markdown.replace(/\[(\d+)\](?!\()/g, "[$1](#cite-$1)");
}

function ExpertAnswerMarkdown({
  markdown,
  citations,
}: {
  markdown: string;
  citations: ExpertCitation[];
}) {
  const citationByIndex = useMemo(
    () => new Map(citations.map((c) => [c.source_index, c])),
    [citations],
  );
  const linked = useMemo(() => linkifyCitationMarkers(markdown), [markdown]);

  return (
    <Markdown
      components={{
        a: ({ href, children }) => {
          if (href?.startsWith("#cite-")) {
            const idx = Number.parseInt(href.slice("#cite-".length), 10);
            const citation = citationByIndex.get(idx);
            if (citation) {
              return <CitationChip citation={citation} index={idx} />;
            }
          }
          return (
            <a href={href} className="text-accent hover:underline">
              {children}
            </a>
          );
        },
      }}
    >
      {linked}
    </Markdown>
  );
}

function CopyAnswerButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      type="button"
      onClick={() => void copy()}
      data-testid="expert-copy-answer"
    >
      {copied ? "Copied" : "Copy"}
    </Button>
  );
}

function LogToChatterButton({
  connectionId,
  model,
  resId,
  body,
}: {
  connectionId: string;
  model: string;
  resId: number;
  body: string;
}) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  async function post() {
    if (!window.confirm("Log this Expert answer as an internal note on the Odoo record?")) return;
    setBusy(true);
    setNote(null);
    try {
      const res = await api.expertPostToChatter({
        connection_id: connectionId,
        model,
        res_id: resId,
        body_markdown: body,
        confirmed: true,
      });
      setNote(res.message);
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Failed to post note");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        loading={busy}
        data-testid="expert-log-chatter"
        onClick={() => void post()}
      >
        Log as Odoo note
      </Button>
      {note ? <span className="text-xs text-muted">{note}</span> : null}
    </div>
  );
}

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
  const [turns, setTurns] = useState<Turn[]>([]);
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

  const canLogToChatter = Boolean(uiContext.model && uiContext.resId && uiContext.resId > 0);

  useEffect(() => {
    setTurns(loadThread(connectionId));
  }, [connectionId]);

  const contextLabel = useMemo(() => {
    if (!contextEnabled) return null;
    const parts: string[] = [];
    if (uiContext.model) parts.push(uiContext.model);
    if (uiContext.draftSummary) parts.push("draft");
    if (uiContext.route) parts.push(uiContext.route.split("/").pop() ?? "");
    return parts.length ? parts.join(" · ") : null;
  }, [contextEnabled, uiContext]);

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
      const priorTurns = opts?.freshThread ? [] : turns;
      const conversation = priorTurns.map((t) => ({
        role: t.role,
        content: t.role === "assistant" ? t.response?.answer_markdown ?? t.content : t.content,
      }));
      const userTurn: Turn = { role: "user", content: q };
      setTurns((prev) => {
        const base = opts?.freshThread ? [] : prev;
        const next = [...base, userTurn];
        saveThread(connectionId, next);
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
          const next: Turn[] = [
            ...prev,
            { role: "assistant", content: response.answer_markdown, response },
          ];
          saveThread(connectionId, next);
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
    if (!window.confirm("Clear this Expert conversation?")) return;
    setTurns([]);
    setError(null);
    setInput("");
    setErrorPaste("");
    clearThread(connectionId);
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
      saveThread(connectionId, []);
    }
    if (seedResponse) {
      const userQ = seedQuestion?.trim() || question.trim() || "Explain this";
      const seeded: Turn[] = [
        { role: "user", content: userQ },
        {
          role: "assistant",
          content: seedResponse.answer_markdown,
          response: seedResponse,
        },
      ];
      setTurns(seeded);
      saveThread(connectionId, seeded);
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
      description="Answers cite their sources — and say so when they don't know."
      testId="expert-panel"
      className="max-w-lg"
    >
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="border-b border-border-subtle px-4 py-2">
          <div className="flex items-center justify-between gap-2">
            {contextLabel ? (
              <div className="flex min-w-0 flex-1 items-center gap-2 text-xs">
                <span className="truncate text-muted">
                  Using context: <span className="text-ink">{contextLabel}</span>
                </span>
                <button
                  type="button"
                  className="shrink-0 text-accent hover:underline"
                  onClick={() => setContextEnabled(!contextEnabled)}
                  data-testid="expert-context-toggle"
                >
                  {contextEnabled ? "Turn off" : "Turn on"}
                </button>
              </div>
            ) : (
              <span className="text-xs text-muted">Expert conversation</span>
            )}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={turns.length === 0 || busy}
              data-testid="expert-clear-history"
              onClick={clearHistory}
            >
              Clear history
            </Button>
          </div>
          {!errorInMainInput ? (
            <>
              <label className="mt-2 block text-xs font-medium text-muted" htmlFor="expert-error-paste">
                Paste an error to diagnose (optional)
              </label>
              <textarea
                id="expert-error-paste"
                className="mt-1 w-full rounded-md border border-border-subtle bg-surface px-2 py-1.5 text-xs font-mono"
                rows={2}
                value={errorPaste}
                onChange={(e) => setErrorPaste(e.target.value)}
                placeholder="AccessError, KeyError, RPC traceback…"
                data-testid="expert-error-paste"
              />
            </>
          ) : (
            <p className="mt-2 text-xs text-muted">
              Error details are included in your question below.
            </p>
          )}
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
          {turns.length === 0 ? (
            <Callout variant="info" title="Ask about Odoo or this connection">
              Connect docs, instance metadata, and your current page context when enabled.
            </Callout>
          ) : null}
          {turns.length === 0 && (promptsQuery.data?.length ?? 0) > 0 ? (
            <div className="flex flex-wrap gap-2" data-testid="expert-suggested-prompts">
              {promptsQuery.data!.map((p) => (
                <Button
                  key={p.id}
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => void sendQuestion(p.question, { freshThread: true })}
                >
                  {p.label}
                </Button>
              ))}
            </div>
          ) : null}
          {turns.map((turn, idx) => (
            <div
              key={`${turn.role}-${idx}`}
              className={cn(
                "flex gap-2 text-sm",
                turn.role === "user" ? "justify-end" : "justify-start",
              )}
            >
              {turn.role === "assistant" ? (
                <div
                  className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-accent to-accent-hover text-[10px] font-semibold text-on-accent shadow-sm"
                  aria-hidden
                >
                  AI
                </div>
              ) : null}
              <div
                className={cn(
                  "max-w-[92%] rounded-2xl px-3 py-2.5 shadow-sm",
                  turn.role === "user"
                    ? "rounded-br-md bg-gradient-to-br from-accent to-accent-hover text-on-accent"
                    : "rounded-bl-md border border-border-subtle bg-gradient-to-b from-surface-raised to-surface text-ink",
                )}
              >
              {turn.role === "assistant" && turn.response ? (
                <>
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap gap-2">
                      {turn.response.declined ? (
                        <Badge variant="warning">Declined</Badge>
                      ) : turn.response.grounded ? (
                        <Badge variant="success">Grounded</Badge>
                      ) : null}
                    {turn.response.caution_flags?.map((f) => (
                        <Badge key={f} variant="warning">
                          {f === "rule_based_diagnosis" ? "Rule-based fix" : f}
                        </Badge>
                      ))}
                    </div>
                    <CopyAnswerButton text={turn.response.answer_markdown} />
                  </div>
                  {canLogToChatter && turn.role === "assistant" ? (
                    <div className="mb-2">
                      <LogToChatterButton
                        connectionId={connectionId}
                        model={uiContext.model!}
                        resId={uiContext.resId!}
                        body={turn.response.answer_markdown}
                      />
                    </div>
                  ) : null}
                  <div className="prose prose-sm max-w-none dark:prose-invert">
                    <ExpertAnswerMarkdown
                      markdown={turn.response.answer_markdown}
                      citations={turn.response.citations ?? []}
                    />
                  </div>
                  {turn.response.citations?.length ? (
                    <div className="mt-3 border-t border-border-subtle pt-2">
                      <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted">
                        Sources
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {turn.response.citations.map((c) => (
                          <CitationChip key={c.chunk_id} citation={c} />
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {turn.response.suggested_tools?.length ? (
                    <div className="mt-3 space-y-1">
                      {turn.response.suggested_tools.map((tool) => (
                        <a
                          key={tool.id ?? tool.label}
                          href={tool.deep_link ?? "#"}
                          className="flex items-center gap-1 text-xs text-accent hover:underline"
                        >
                          <ExternalLink className="h-3 w-3" />
                          {tool.label ?? tool.id}
                        </a>
                      ))}
                    </div>
                  ) : null}
                </>
              ) : (
                turn.content
              )}
              </div>
            </div>
          ))}
          {error ? (
            <Callout variant="danger" title="Expert unavailable">
              {error}
            </Callout>
          ) : null}
          <div ref={bottomRef} />
        </div>

        <form
          className="border-t border-border-subtle p-4"
          onSubmit={(e) => {
            e.preventDefault();
            void sendQuestion(input);
          }}
        >
          <textarea
            className="w-full rounded-md border border-border-subtle bg-surface px-3 py-2 text-sm"
            rows={3}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about Odoo, this model, or an error…"
            data-testid="expert-input"
          />
          <div className="mt-2 flex justify-end gap-2">
            <Button type="submit" variant="primary" loading={busy} disabled={!input.trim()}>
              Ask Expert
            </Button>
          </div>
        </form>
      </div>
    </Sheet>
  );
}
