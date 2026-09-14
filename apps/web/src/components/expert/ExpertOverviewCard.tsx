"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import { useShellOptional } from "@/context/ShellContext";
import {
  EXPERT_HONESTY_LINE,
  EXPERT_STARTER_PROMPTS,
  expertHonestyLegend,
  expertOverviewBody,
  expertOverviewKicker,
  expertOverviewTitle,
} from "@/lib/expert-journey";

type ExpertOverviewCardProps = {
  connectionId: string;
  connectionName?: string | null;
  onAsk?: (question: string) => void;
};

export function ExpertOverviewCard({
  connectionId,
  connectionName,
  onAsk,
}: ExpertOverviewCardProps) {
  const shell = useShellOptional();

  function ask(question: string) {
    if (onAsk) {
      onAsk(question);
      return;
    }
    shell?.openExpert({ question, autoSubmit: true, freshThread: true });
  }

  return (
    <Card className="expert-overview-card mb-6 p-5" data-testid="expert-overview-card">
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
        {expertOverviewKicker()}
        {connectionName ? ` · ${connectionName}` : ""}
      </p>
      <h2 className="mt-1 text-lg font-semibold tracking-tight text-ink">{expertOverviewTitle()}</h2>
      <p className="mt-1 text-sm text-muted">{expertOverviewBody()}</p>
      <p className="expert-honesty-line mt-3" data-testid="expert-overview-honesty">
        {EXPERT_HONESTY_LINE}
      </p>
      <ul className="mt-3 space-y-0.5 text-[11px] text-muted" data-testid="expert-overview-legend">
        {expertHonestyLegend().map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      <div className="mt-4 flex flex-wrap gap-2" data-testid="expert-overview-starters">
        {EXPERT_STARTER_PROMPTS.map((prompt) => (
          <Button
            key={prompt.id}
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => ask(prompt.question)}
          >
            {prompt.label}
          </Button>
        ))}
        <Button type="button" variant="primary" size="sm" onClick={() => shell?.openExpert()}>
          Open Expert
        </Button>
      </div>
      <div className="job-handoff-bar mt-4">
        <Button asChild variant="ghost" size="sm">
          <Link href={`/connections/${connectionId}/wizard`}>Draft Studio</Link>
        </Button>
        <Button asChild variant="ghost" size="sm">
          <Link href={`/connections/${connectionId}/designer`}>View Designer</Link>
        </Button>
        <Button asChild variant="ghost" size="sm">
          <Link href={`/connections/${connectionId}/projects`}>Projects</Link>
        </Button>
        <Button asChild variant="ghost" size="sm">
          <Link href={`/connections/${connectionId}/modulespec`}>ModuleSpec</Link>
        </Button>
        <Button asChild variant="ghost" size="sm">
          <Link href={`/connections/${connectionId}/job`}>Job Autopilot</Link>
        </Button>
      </div>
    </Card>
  );
}
