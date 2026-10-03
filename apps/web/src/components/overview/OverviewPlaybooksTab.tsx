"use client";

import { DomainPlaybooksPanel } from "@/components/DomainPlaybooksPanel";
import { EePlaybooksPanel } from "@/components/EePlaybooksPanel";
import { StudioFeatureRecipesPanel } from "@/components/StudioFeatureRecipesPanel";
import { Card } from "@/components/ui/layout-primitives";
import { Disclosure } from "@/components/ui/Disclosure";
import type { OverviewPageModel } from "./use-overview-page";

export function OverviewPlaybooksTab({ vm }: { vm: OverviewPageModel }) {
  return (
    <div className="space-y-3">
      <Disclosure title="Enterprise playbooks" defaultOpen={false}>
        <EePlaybooksPanel connectionId={vm.connectionId} />
      </Disclosure>
      <Disclosure title="Domain playbooks" defaultOpen={false}>
        <DomainPlaybooksPanel connectionId={vm.connectionId} />
      </Disclosure>
      <Disclosure title="Studio feature recipes" defaultOpen={false}>
        <StudioFeatureRecipesPanel />
      </Disclosure>
      {vm.libraryStats?.available && (
        <Card className="flex flex-wrap gap-6 p-4 text-sm">
          <span className="font-medium text-ink">Library</span>
          <span>
            <span className="text-muted">Books </span>
            <span className="font-mono text-accent">{vm.libraryStats.books ?? "—"}</span>
          </span>
          <span>
            <span className="text-muted">Loans </span>
            <span className="font-mono text-accent">{vm.libraryStats.loans ?? "—"}</span>
          </span>
          <span>
            <span className="text-muted">Active </span>
            <span className="font-mono text-accent">{vm.libraryStats.active_loans ?? "—"}</span>
          </span>
          <span>
            <span className="text-muted">Overdue </span>
            <span className="font-mono text-danger">{vm.libraryStats.overdue_loans ?? "—"}</span>
          </span>
        </Card>
      )}
    </div>
  );
}
