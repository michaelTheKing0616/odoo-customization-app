"use client";

import { ArchDrawing } from "@/components/brand/ArchDrawing";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";

type Props = {
  connectionId: string;
  modelCount: number;
};

function storageKey(connectionId: string) {
  return `overview-first-run-dismissed-${connectionId}`;
}

type Step = { key: string; label: string; href?: string; note: string; testId?: string };

function doneKey(connectionId: string) {
  return `overview-first-run-done-${connectionId}`;
}

/** Touch 129: satisfying checklist. Steps strike through with a drawn line; when all are done
 * the list folds into one "Setup complete" stone. A step counts once you have opened it. */
export function FirstRunCard({ connectionId, modelCount }: Props) {
  const [dismissed, setDismissed] = useState(true);
  const [done, setDone] = useState<string[]>([]);

  useEffect(() => {
    if (modelCount > 0) return;
    try {
      setDismissed(localStorage.getItem(storageKey(connectionId)) === "1");
      setDone(JSON.parse(localStorage.getItem(doneKey(connectionId)) ?? "[]") as string[]);
    } catch {
      setDismissed(false);
    }
  }, [connectionId, modelCount]);

  if (modelCount > 0 || dismissed) return null;

  const steps: Step[] = [
    { key: "connect", label: "Connect", note: "this database is linked." },
    { key: "studio", label: "App Studio", href: `/connections/${connectionId}/studio`, note: "describe the work, then review before anything writes to Odoo.", testId: "overview-first-run-app-studio" },
    { key: "projects", label: "Projects", href: `/connections/${connectionId}/projects`, note: "track drafts and open ModuleSpec or Job Autopilot from the board when you need them.", testId: "overview-first-run-projects" },
    { key: "builder", label: "Apply in Builder", href: `/connections/${connectionId}/builder`, note: "create models and fields, or export as a module." },
  ];
  const isDone = (k: string) => k === "connect" || done.includes(k);
  const mark = (k: string) => {
    const next = Array.from(new Set([...done, k]));
    setDone(next);
    try {
      localStorage.setItem(doneKey(connectionId), JSON.stringify(next));
    } catch {
      /* stays in memory */
    }
  };
  const allDone = steps.every((st) => isDone(st.key));

  if (allDone) {
    return (
      <Card className="mt-6 flex items-center gap-3 p-4 setup-stone" data-testid="overview-first-run">
        <svg width="18" height="16" viewBox="0 0 18 16" aria-hidden="true"><path d="M3 0h12l-3 16H6z" fill="var(--brand-cinnabar)" /></svg>
        <span className="text-sm font-semibold text-ink" data-testid="overview-first-run-complete">Setup complete</span>
        <Button type="button" variant="ghost" size="sm" className="ml-auto" onClick={() => { localStorage.setItem(storageKey(connectionId), "1"); setDismissed(true); }} data-testid="overview-first-run-dismiss">
          Hide
        </Button>
      </Card>
    );
  }

  return (
    <Card className="mt-6 p-5" data-testid="overview-first-run">
      <div className="flex items-start justify-between gap-4">
        <h2 className="text-lg font-semibold text-ink">Start here</h2>
        <ArchDrawing width={84} progress={{ done: steps.filter((st) => isDone(st.key)).length, total: steps.length }} />
      </div>
      <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-muted">
        {steps.map((st) => (
          <li key={st.key} className="setup-step" data-done={isDone(st.key) ? "" : undefined}>
            <span className="setup-step-text">
              {st.href ? (
                <Link href={st.href} onClick={() => mark(st.key)} className="font-medium text-ink underline underline-offset-2" data-testid={st.testId}>
                  {st.label}
                </Link>
              ) : (
                <span className="text-ink">{st.label}</span>
              )}
              : {st.note}
            </span>
          </li>
        ))}
      </ol>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="mt-4"
        onClick={() => {
          localStorage.setItem(storageKey(connectionId), "1");
          setDismissed(true);
        }}
        data-testid="overview-first-run-dismiss"
      >
        Dismiss
      </Button>
    </Card>
  );
}
