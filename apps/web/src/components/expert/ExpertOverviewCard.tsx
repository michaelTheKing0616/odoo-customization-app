"use client";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import { useShellOptional } from "@/context/ShellContext";
import {
  EXPERT_HONESTY_LINE,
  EXPERT_STARTER_PROMPTS,
  expertHonestyLegend,
  expertOverviewBody,
  expertOverviewTitle,
} from "@/lib/expert-journey";
import { BuildSpineBar } from "@/components/build/BuildSpineBar";

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
      <h2 className="expert-overview-title">
        {expertOverviewTitle()}
        {connectionName ? <span className="expert-overview-conn">{connectionName}</span> : null}
      </h2>
      <p className="mt-1 text-sm text-muted">{expertOverviewBody()}</p>
      <p className="expert-honesty-line mt-3" data-testid="expert-overview-honesty">
        {EXPERT_HONESTY_LINE}
      </p>
      <ul className="expert-honesty-legend mt-2" data-testid="expert-overview-legend">
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
        <Button
          type="button"
          variant="primary"
          size="sm"
          onClick={() => shell?.openExpert()}
        >
          Open Expert
        </Button>
      </div>
      <div className="mt-4">
        <BuildSpineBar connectionId={connectionId} compact />
      </div>
    </Card>
  );
}
