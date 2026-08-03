"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Markdown from "react-markdown";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Sheet } from "@/components/ui/Sheet";
import { ExternalLink } from "@/components/ui/icons";
import { Tooltip } from "@/components/ui/Tooltip";
import { useShell } from "@/context/ShellContext";
import { api, type ExpertAskResponse, type ExpertCitation } from "@/lib/api";
import { cn } from "@/lib/cn";

type Turn = { role: "user" | "assistant"; content: string; response?: ExpertAskResponse };

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

function CitationChip({ citation }: { citation: ExpertCitation }) {
  return (
    <Tooltip
      label={`${citation.source} · ${citation.version} — ${citation.breadcrumb}`}
    >
      <sup className="cursor-help rounded bg-accent-subtle px-1 text-[10px] text-accent">
        [{citation.chunk_id.slice(0, 6)}]
      </sup>
    </Tooltip>
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
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setTurns(loadThread(connectionId));
  }, [connectionId]);

  useEffect(() => {
    if (expertPrefill?.question) {
      setInput(expertPrefill.question);
    }
    if (expertPrefill?.errorText) {
      setErrorPaste(expertPrefill.errorText);
    }
    clearExpertPrefill();
  }, [expertPrefill, clearExpertPrefill]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, busy]);

  const contextLabel = useMemo(() => {
    if (!contextEnabled) return null;
    const parts: string[] = [];
    if (uiContext.model) parts.push(uiContext.model);
    if (uiContext.draftSummary) parts.push("draft");
    if (uiContext.route) parts.push(uiContext.route.split("/").pop() ?? "");
    return parts.length ? parts.join(" · ") : null;
  }, [contextEnabled, uiContext]);

  async function sendQuestion(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    setBusy(true);
    setError(null);
    const conversation = turns.map((t) => ({
      role: t.role,
      content: t.role === "assistant" ? t.response?.answer_markdown ?? t.content : t.content,
    }));
    const userTurn: Turn = { role: "user", content: q };
    setTurns((prev) => {
      const next = [...prev, userTurn];
      saveThread(connectionId, next);
      return next;
    });
    setInput("");
    try {
      const ui_context = contextEnabled
        ? {
            ...uiContext,
            ...(errorPaste.trim() ? { pasted_error: errorPaste.trim() } : {}),
          }
        : errorPaste.trim()
          ? { pasted_error: errorPaste.trim() }
          : undefined;
      const response = await api.expertAsk({
        question: errorPaste.trim() ? `${q}\n\nError log:\n${errorPaste.trim()}` : q,
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
  }

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
                  <div className="mb-2 flex flex-wrap gap-2">
                    {turn.response.declined ? (
                      <Badge variant="warning">Declined</Badge>
                    ) : turn.response.grounded ? (
                      <Badge variant="success">Grounded</Badge>
                    ) : null}
                    {turn.response.caution_flags?.map((f) => (
                      <Badge key={f} variant="warning">
                        {f}
                      </Badge>
                    ))}
                  </div>
                  <div className="prose prose-sm max-w-none dark:prose-invert">
                    <Markdown>{turn.response.answer_markdown}</Markdown>
                  </div>
                  {turn.response.citations?.length ? (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {turn.response.citations.map((c) => (
                        <CitationChip key={c.chunk_id} citation={c} />
                      ))}
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
