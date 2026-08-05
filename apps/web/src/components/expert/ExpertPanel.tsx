"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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

  useEffect(() => {
    if (!expertPrefill?.question) return;
    const { question, errorText, autoSubmit, freshThread } = expertPrefill;
    const prompt = formatExpertDiagnosePrompt(question, errorText);
    setInput(prompt);
    setErrorPaste(errorText?.trim() ?? "");
    if (freshThread) {
      setTurns([]);
      saveThread(connectionId, []);
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
          {contextLabel ? (
            <div className="flex items-center justify-between gap-2 text-xs">
              <span className="text-muted">
                Using context: <span className="text-ink">{contextLabel}</span>
              </span>
              <button
                type="button"
                className="text-accent hover:underline"
                onClick={() => setContextEnabled(!contextEnabled)}
                data-testid="expert-context-toggle"
              >
                {contextEnabled ? "Turn off" : "Turn on"}
              </button>
            </div>
          ) : null}
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
          {turns.map((turn, idx) => (
            <div
              key={`${turn.role}-${idx}`}
              className={cn(
                "rounded-md px-3 py-2 text-sm",
                turn.role === "user"
                  ? "ml-8 bg-accent-subtle text-ink"
                  : "mr-4 border border-border-subtle bg-surface-raised",
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
