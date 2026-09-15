"use client";

import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import type { LiveDemoAnswer } from "@/lib/api";

export type PresenterSseStatus = "connecting" | "connected" | "disconnected";

export type PresenterOverlayProps = {
  answers: LiveDemoAnswer[];
  sseStatus?: PresenterSseStatus;
  sessionId?: string | null;
  /** When false, hide the share-guidance callout (parent already dismissed). */
  showShareGuidance?: boolean;
  onDismissGuidance?: () => void;
};

const GUIDANCE_STORAGE_KEY = "ldc-presenter-overlay-guidance-dismissed";

export function PresenterOverlay({
  answers,
  sseStatus = "connected",
  sessionId,
  showShareGuidance,
  onDismissGuidance,
}: PresenterOverlayProps) {
  const [index, setIndex] = useState(0);
  const [flash, setFlash] = useState(false);
  const [localGuidance, setLocalGuidance] = useState(true);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (localStorage.getItem(GUIDANCE_STORAGE_KEY) === "1") {
      setLocalGuidance(false);
    }
  }, []);

  const guidanceVisible =
    showShareGuidance !== undefined ? showShareGuidance : localGuidance;

  // Newest answers arrive at index 0 — jump there and flash.
  useEffect(() => {
    if (answers.length === 0) return;
    setIndex(0);
    setFlash(true);
    const t = window.setTimeout(() => setFlash(false), 900);
    return () => window.clearTimeout(t);
  }, [answers[0]?.id]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowDown" || e.key === "j") {
        e.preventDefault();
        setIndex((i) => Math.min(i + 1, Math.max(answers.length - 1, 0)));
      } else if (e.key === "ArrowUp" || e.key === "k") {
        e.preventDefault();
        setIndex((i) => Math.max(i - 1, 0));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [answers.length]);

  const active = answers[index] ?? null;
  const sseLabel = useMemo(() => {
    if (sseStatus === "connected") return "Live";
    if (sseStatus === "connecting") return "Connecting…";
    return "Reconnecting…";
  }, [sseStatus]);

  function dismissGuidance() {
    if (onDismissGuidance) {
      onDismissGuidance();
      return;
    }
    localStorage.setItem(GUIDANCE_STORAGE_KEY, "1");
    setLocalGuidance(false);
  }

  return (
    <div
      className="flex min-h-screen flex-col bg-background text-ink"
      data-testid="presenter-overlay"
    >
      <header className="flex items-center justify-between gap-3 border-b border-border-subtle px-4 py-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">
            Presenter overlay · private
          </p>
          <p className="mt-0.5 text-sm font-medium text-ink">Live Demo Co-Pilot</p>
        </div>
        <span data-testid="presenter-not-for-share">
          <Badge variant="warning">Not for screen share</Badge>
        </span>
      </header>

      <div className="flex flex-1 flex-col gap-4 p-4">
        {guidanceVisible ? (
          <Callout variant="warning" title="Keep answers off the client screen">
            <ul className="mt-1 list-disc space-y-1 pl-4 text-sm">
              <li>Share the Zoom / Meet / Teams window, or your Odoo demo tab — not entire screen.</li>
              <li>Leave this overlay on another display, or outside the shared window.</li>
              <li>Never share this window while presenting.</li>
            </ul>
            <div className="mt-3">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={dismissGuidance}
                data-testid="presenter-dismiss-guidance"
              >
                Got it
              </Button>
            </div>
          </Callout>
        ) : null}

        {active ? (
          <article
            className={[
              "rounded-xl border p-5 shadow-sm transition-shadow",
              flash
                ? "border-accent/50 bg-accent/5 shadow-accent/20"
                : "border-border-subtle bg-surface-raised/40",
            ].join(" ")}
            data-testid="presenter-active-answer"
          >
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span data-testid="presenter-confidence">
                <Badge variant={active.confidence === "high" ? "success" : "warning"}>
                  {active.confidence} confidence
                </Badge>
              </span>
              {answers.length > 1 ? (
                <span className="text-xs text-muted">
                  {index + 1} / {answers.length}
                </span>
              ) : null}
            </div>
            <p className="text-sm text-muted" data-testid="presenter-question">
              <span className="font-medium text-accent">
                {active.speaker_name || "Client"}
              </span>
              {" — "}
              {active.question}
            </p>
            {active.confidence_flag ? (
              <p
                className="mt-3 text-sm font-medium text-warning-strong"
                data-testid="presenter-confidence-flag"
              >
                {active.confidence_flag}
              </p>
            ) : null}
            <ul className="mt-4 space-y-3" data-testid="presenter-bullets">
              {active.bullets.map((b) => (
                <li
                  key={b}
                  className="rounded-lg border border-border-subtle/80 bg-surface px-3 py-2.5 text-[15px] leading-snug text-ink"
                >
                  {b}
                </li>
              ))}
            </ul>
            {answers.length > 1 ? (
              <div className="mt-4 flex gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={index <= 0}
                  onClick={() => setIndex((i) => Math.max(i - 1, 0))}
                  data-testid="presenter-newer"
                >
                  Newer
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={index >= answers.length - 1}
                  onClick={() => setIndex((i) => Math.min(i + 1, answers.length - 1))}
                  data-testid="presenter-older"
                >
                  Older
                </Button>
              </div>
            ) : null}
          </article>
        ) : (
          <div
            className="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-border-subtle bg-surface-raised/30 px-6 py-16 text-center"
            data-testid="presenter-empty"
          >
            <p className="text-base font-medium text-ink">Waiting for Odoo questions…</p>
            <p className="mt-2 max-w-sm text-sm text-muted">
              When a client asks something Odoo-related, Stage 1→2 will drop 2–3 private bullets here.
            </p>
          </div>
        )}

        {answers.length > 1 ? (
          <div className="space-y-1.5" data-testid="presenter-history">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">
              Recent
            </p>
            <ul className="max-h-36 space-y-1 overflow-y-auto">
              {answers.slice(0, 10).map((a, i) => (
                <li key={a.id}>
                  <button
                    type="button"
                    className={[
                      "w-full rounded-md px-2.5 py-1.5 text-left text-xs transition-colors",
                      i === index
                        ? "bg-accent/15 text-ink"
                        : "text-muted hover:bg-surface-raised hover:text-ink",
                    ].join(" ")}
                    onClick={() => setIndex(i)}
                  >
                    <span className="font-medium">{a.speaker_name || "Client"}</span>
                    {" · "}
                    {a.question.length > 72 ? `${a.question.slice(0, 72)}…` : a.question}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>

      <footer className="flex items-center justify-between gap-2 border-t border-border-subtle px-4 py-2.5 text-xs text-muted">
        <span data-testid="presenter-sse-status">
          <span
            className={[
              "mr-1.5 inline-block h-1.5 w-1.5 rounded-full",
              sseStatus === "connected"
                ? "bg-success"
                : sseStatus === "connecting"
                  ? "bg-warning"
                  : "bg-danger",
            ].join(" ")}
          />
          {sseLabel}
        </span>
        <span className="truncate font-mono" title={sessionId ?? undefined}>
          {sessionId ? `session ${sessionId.slice(0, 8)}…` : "no session"}
        </span>
        <span className="hidden sm:inline">↑↓ / j k</span>
      </footer>
    </div>
  );
}
