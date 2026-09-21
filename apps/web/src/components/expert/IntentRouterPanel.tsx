"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/layout-primitives";
import { Callout } from "@/components/ui/Callout";
import { api, type IntentRouteMatch, type IntentRouteResult } from "@/lib/api";

type IntentRouterPanelProps = {
  connectionId: string;
};

const STARTERS = [
  "upload 200 journal entries",
  "bulk create customers",
  "upload invoices",
  "lock accounting dates",
  "build a visitor log app",
];

function MatchRow({ match }: { match: IntentRouteMatch }) {
  const pct = Math.round((match.confidence || 0) * 100);
  return (
    <li
      className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-3 sm:flex-row sm:items-center sm:justify-between"
      data-testid="intent-route-match"
    >
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-ink">{match.title}</p>
        <p className="mt-0.5 text-xs text-muted">{match.why}</p>
        <p className="mt-1 font-mono text-[11px] text-accent">{match.deep_link}</p>
        <p className="mt-0.5 text-[11px] text-muted">
          Confidence {pct}%
          {match.recipe ? ` · ${match.recipe}` : ""}
          {match.can_handle === "partial" ? " · partial" : ""}
        </p>
      </div>
      <Button asChild variant="primary" size="sm" data-testid="intent-route-go">
        <Link href={match.deep_link}>Go</Link>
      </Button>
    </li>
  );
}

export function IntentRouterPanel({ connectionId }: IntentRouterPanelProps) {
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IntentRouteResult | null>(null);

  const run = useCallback(
    async (text?: string) => {
      const q = (text ?? prompt).trim();
      if (!q || busy) return;
      setBusy(true);
      setError(null);
      try {
        const out = await api.expertIntentRoute(connectionId, { prompt: q, limit: 5 });
        setResult(out);
        if (text) setPrompt(text);
      } catch (err) {
        setResult(null);
        setError(err instanceof Error ? err.message : "Intent route failed");
      } finally {
        setBusy(false);
      }
    },
    [busy, connectionId, prompt],
  );

  const unsupported = result?.can_handle === "false";
  const matches = [...(result?.matches || []), ...(result?.alternatives || [])];

  return (
    <Card className="mb-6 space-y-4 p-5" data-testid="intent-router-panel">
      <div>
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
          Intent → feature
        </p>
        <h2 className="mt-1 text-lg font-semibold tracking-tight text-ink">
          What do you want to do?
        </h2>
        <p className="mt-1 text-sm text-muted">
          Describe a goal in plain language. ingenium routes you to a shipped feature — or says
          honestly if it cannot handle it. Preview ≠ posted.
        </p>
      </div>

      <form
        className="flex flex-col gap-2 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault();
          void run();
        }}
      >
        <Input
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="e.g. upload 200 journal entries, bulk create customers…"
          aria-label="What do you want to do?"
          data-testid="intent-router-input"
          className="flex-1"
        />
        <Button
          type="submit"
          variant="primary"
          disabled={busy || !prompt.trim()}
          data-testid="intent-router-submit"
        >
          {busy ? "Routing…" : "Find feature"}
        </Button>
      </form>

      <div className="flex flex-wrap gap-2" data-testid="intent-router-starters">
        {STARTERS.map((s) => (
          <Button
            key={s}
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => void run(s)}
            disabled={busy}
          >
            {s}
          </Button>
        ))}
      </div>

      {error ? (
        <Callout variant="danger" title="Route failed">
          {error}
        </Callout>
      ) : null}

      {result ? (
        <div className="space-y-3" data-testid="intent-router-results">
          {unsupported ? (
            <Callout
              variant="warning"
              title="Not supported in ingenium"
              testId="intent-router-unsupported"
            >
              <p>{result.message}</p>
              {result.honesty ? (
                <p className="mt-2 text-xs text-muted">{result.honesty}</p>
              ) : null}
            </Callout>
          ) : (
            <>
              <p className="text-sm text-ink" data-testid="intent-router-message">
                {result.message}
              </p>
              {result.can_handle === "partial" ? (
                <Callout variant="warning" title="Partial match" testId="intent-router-partial">
                  Closest shipped features are listed — confirm before proceeding. Preview ≠ posted.
                </Callout>
              ) : null}
              {result.ambiguous ? (
                <p className="text-xs text-muted" data-testid="intent-router-ambiguous">
                  Several features could fit — pick the best Go link below.
                </p>
              ) : null}
              <ul className="space-y-2" data-testid="intent-router-matches">
                {matches.map((m) => (
                  <MatchRow key={`${m.feature_id}-${m.deep_link}`} match={m} />
                ))}
              </ul>
              {result.honesty ? (
                <p className="text-[11px] text-muted" data-testid="intent-router-honesty">
                  {result.honesty}
                </p>
              ) : null}
            </>
          )}
        </div>
      ) : null}
    </Card>
  );
}
