"use client";

import { IconExpert } from "@/components/ui/icons";
import { EXPERT_HONESTY_LINE, expertHeaderDescription } from "@/lib/expert-journey";

type ExpertHeaderProps = {
  connectionName?: string | null;
};

export function ExpertHeader({ connectionName }: ExpertHeaderProps) {
  return (
    <div className="expert-header-copy" data-testid="expert-header">
      <div className="flex items-start gap-3">
        <span className="expert-header-mark" aria-hidden>
          <IconExpert className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <p className="expert-header-title">Odoo Expert</p>
          <p className="expert-header-description" data-testid="expert-header-description">
            {expertHeaderDescription(connectionName)}
          </p>
          <p className="expert-honesty-line" data-testid="expert-honesty-line">
            {EXPERT_HONESTY_LINE}
          </p>
        </div>
      </div>
    </div>
  );
}
