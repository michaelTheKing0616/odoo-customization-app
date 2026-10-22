"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { StageProgress } from "@/components/progress/StageProgress";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, EmptyState } from "@/components/ui/layout-primitives";
import { newProgressRunId } from "@/lib/progress/run-id";
import { Callout } from "@/components/ui/Callout";
import { api, type IntentRouteMatch, type IntentRouteResult } from "@/lib/api";
import { stashBuildSpineHandoff } from "@/lib/build-spine-handoff";
import { resolveBuildModeLocal } from "@/lib/build-spine";

type IntentRouterPanelProps = {
  connectionId: string;
  /** `rail` is the compact side-rail form on the Expert page (4 starters, tighter type). */
  variant?: "card" | "rail";
};

/** Routing prompts sent as-is; the chip shows them in sentence case. */
const STARTERS = [
  "upload 200 journal entries",
  "bulk create customers",
  "upload invoices",
  "upload sales orders",
  "lock accounting dates",
  "tax pack",
  "settings board",
  "build a visitor log app",
];

function sentenceCase(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function MatchRow({
  match,
  connectionId,
  prompt,
}: {
  match: IntentRouteMatch;
  connectionId: string;
  prompt: string;
}) {
  const pct = Math.round((match.confidence || 0) * 100);
  function onGo() {
    const fid = String(match.feature_id || "");
    const src = String(match.source || "");
    const isAtlas =
      src === "atlas" ||
      src === "batch_os" ||
      src === "recipe" ||
      Boolean(match.atlas_class) ||
      Boolean(match.recipe);
    const mode = fid.includes("designer")
      ? resolveBuildModeLocal({ grain: "field_pack", artifact_kind: "field_pack" })
      : isAtlas || fid.includes("job") || fid.includes("journal") || fid.includes("config")
        ? resolveBuildModeLocal({ capability: "stock_reuse", artifact_kind: "stock_config" })
        : resolveBuildModeLocal({ capability: "residual_app", grain: "full_app" });
    if (prompt.trim()) {
      stashBuildSpineHandoff(connectionId, {
        version: 1,
        brief: prompt.trim(),
        prompt: prompt.trim(),
        build_mode: mode,
        capability: isAtlas ? "stock_reuse" : undefined,
        grain: isAtlas ? "stock" : undefined,
        delivery_lane: isAtlas ? "online_metadata" : undefined,
        artifact_kind: isAtlas ? "stock_config" : undefined,
        atlas_class: match.atlas_class ?? null,
        recipe_id: match.recipe ?? null,
        risk: match.risk ?? null,
      });
    }
  }
  return (
    <li className="intent-match" data-testid="intent-route-match">
      <div className="min-w-0 flex-1">
        <p className="intent-match-title">{match.title}</p>
        <p className="intent-match-why">{match.why}</p>
        <p className="intent-match-meta">
          <span className="intent-match-path" title={match.deep_link}>
            {match.deep_link}
          </span>
          <span>
            Confidence <span className="tabular-nums">{pct}%</span>
            {match.recipe ? ` · ${match.recipe}` : ""}
            {match.can_handle === "partial" ? " · partial" : ""}
          </span>
        </p>
      </div>
      <Button asChild variant="secondary" size="sm" data-testid="intent-route-go">
        <Link href={match.deep_link} onClick={onGo} aria-label={`Open ${match.title}`}>
          Open
        </Link>
      </Button>
    </li>
  );
}

export function IntentRouterPanel({ connectionId, variant = "card" }: IntentRouterPanelProps) {
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IntentRouteResult | null>(null);
  const [routeHydrated, setRouteHydrated] = useState(true);
  const [progressRunId, setProgressRunId] = useState<string | null>(null);

  const run = useCallback(
    async (text?: string) => {
      const q = (text ?? prompt).trim();
      if (!q || busy) return;
      setRouteHydrated(false);
      setBusy(true);
      setError(null);
      const runId = newProgressRunId("intent");
      setProgressRunId(runId);
      try {
        const out = await api.expertIntentRoute(connectionId, {
          prompt: q,
          limit: 5,
          progress_run_id: runId,
        });
        setResult(out);
        if (text) setPrompt(text);
      } catch (err) {
        setResult(null);
        setError(err instanceof Error ? err.message : "Intent route failed");
      } finally {
        setBusy(false);
        setRouteHydrated(true);
        setProgressRunId(null);
      }
    },
    [busy, connectionId, prompt],
  );

  const unsupported = result?.can_handle === "false";
  const matches = [...(result?.matches || []), ...(result?.alternatives || [])];
  const starters = variant === "rail" ? STARTERS.slice(0, 4) : STARTERS;

  return (
    <Card
      className={variant === "rail" ? "intent-router intent-router--rail" : "intent-router mb-6"}
      data-testid="intent-router-panel"
    >
      <div>
        <h2 className="intent-router-title">What do you want to do?</h2>
        <p className="intent-router-body">
          Describe a goal. Expert points you to the ingenium screen that does it, or says plainly
          that it can&apos;t. Nothing is written from here.
        </p>
      </div>

      <form
        className="intent-router-form"
        onSubmit={(e) => {
          e.preventDefault();
          void run();
        }}
      >
        <Input
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Upload 200 journal entries…"
          aria-label="What do you want to do?"
          data-testid="intent-router-input"
          className="min-w-0 flex-1"
        />
        <Button
          type="submit"
          variant="secondary"
          disabled={busy || !prompt.trim()}
          data-testid="intent-router-submit"
        >
          {busy ? "Routing…" : "Find feature"}
        </Button>
      </form>

      <ul className="intent-router-starters" data-testid="intent-router-starters" aria-label="Example goals">
        {starters.map((s) => (
          <li key={s}>
            <button
              type="button"
              className="intent-starter"
              onClick={() => void run(s)}
              disabled={busy}
            >
              {sentenceCase(s)}
            </button>
          </li>
        ))}
      </ul>

      {error ? (
        <Callout variant="danger" title="Could not route this goal" testId="intent-router-error">
          <p>{error}</p>
          <p className="mt-1">Try again, or ask the question in the Expert conversation.</p>
        </Callout>
      ) : null}

      {busy && !routeHydrated ? (
        <StageProgress
          runId={progressRunId}
          active
          fallbackLabel="Routing your goal…"
          onStop={() => setBusy(false)}
        />
      ) : null}

      {result && routeHydrated ? (
        <div className="intent-router-results" data-testid="intent-router-results">
          {unsupported ? (
            <Callout
              variant="warning"
              title="Not supported in ingenium"
              testId="intent-router-unsupported"
            >
              <p>{result.message}</p>
              {result.honesty ? (
                <p className="mt-2 text-xs">{result.honesty}</p>
              ) : null}
            </Callout>
          ) : (
            <>
              <p className="intent-router-message" data-testid="intent-router-message">
                {result.message}
              </p>
              {result.can_handle === "partial" ? (
                <Callout variant="warning" title="Partial match" testId="intent-router-partial">
                  These are the closest shipped features. Check the fit before you continue.
                  Preview is not posted.
                </Callout>
              ) : null}
              {result.ambiguous ? (
                <p className="intent-router-note" data-testid="intent-router-ambiguous">
                  Several features could fit. Open the one that matches your goal.
                </p>
              ) : null}
              {matches.length === 0 ? (
                <div data-testid="intent-router-matches-empty">
                  <EmptyState
                    title="No shipped feature matched"
                    description="Rephrase the goal or pick an example, then route again."
                    action={
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        disabled={busy || !prompt.trim()}
                        onClick={() => void run()}
                      >
                        Route again
                      </Button>
                    }
                  />
                </div>
              ) : (
                <ul className="intent-match-list" data-testid="intent-router-matches">
                  {matches.map((m) => (
                    <MatchRow
                      key={`${m.feature_id}-${m.deep_link}`}
                      match={m}
                      connectionId={connectionId}
                      prompt={prompt}
                    />
                  ))}
                </ul>
              )}
              {result.honesty ? (
                <p className="intent-router-note" data-testid="intent-router-honesty">
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
