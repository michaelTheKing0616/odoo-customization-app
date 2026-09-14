"use client";

import { IconExpert } from "@/components/ui/icons";
import {
  EXPERT_HONESTY_LINE,
  expertHeaderDescription,
  expertOverviewKicker,
} from "@/lib/expert-journey";

type ExpertHeaderProps = {
  connectionName?: string | null;
};

export function ExpertHeader({ connectionName }: ExpertHeaderProps) {
  return (
    <div className="expert-header-copy" data-testid="expert-header">
      <div className="flex items-start gap-3">
        <span
          className="expert-header-mark mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
          aria-hidden
        >
          <IconExpert className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <p className="expert-header-kicker">{expertOverviewKicker()}</p>
          <p className="text-[15px] font-semibold tracking-tight text-ink">Odoo Expert</p>
          <p className="mt-0.5 text-xs leading-5 text-muted" data-testid="expert-header-description">
            {expertHeaderDescription(connectionName)}
          </p>
        </div>
      </div>
      <p className="expert-honesty-line mt-3" data-testid="expert-honesty-line">
        {EXPERT_HONESTY_LINE}
      </p>
    </div>
  );
}
