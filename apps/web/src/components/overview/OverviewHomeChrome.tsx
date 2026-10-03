"use client";

import Link from "next/link";
import { BuildSpineBar } from "@/components/build/BuildSpineBar";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import { FirstRunCard } from "@/components/overview/FirstRunCard";
import { InstanceFingerprintCard } from "@/components/overview/InstanceFingerprintCard";
import type { OverviewPageModel } from "./use-overview-page";

export function OverviewHomeChrome({ vm }: { vm: OverviewPageModel }) {
  return (
    <>
      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Models", value: vm.models.length },
          { label: "Apps", value: vm.modules.length },
          { label: "Promoted", value: vm.promoted.length },
          { label: "Fields (current)", value: vm.tab === "fields" ? vm.fields.length : "—" },
        ].map((stat) => (
          <Card key={stat.label} className="p-4">
            <p className="text-xs text-muted">{stat.label}</p>
            <p className="mt-1 text-2xl font-semibold text-ink">{stat.value}</p>
          </Card>
        ))}
      </div>

      <div className="mt-6" data-testid="overview-build-spine">
        <BuildSpineBar connectionId={vm.connectionId} />
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="primary" size="sm" asChild>
          <Link href={`/connections/${vm.connectionId}/studio`} data-testid="overview-draft-with-ai">
            App Studio
          </Link>
        </Button>
        <Button variant="secondary" size="sm" asChild>
          <Link href={`/connections/${vm.connectionId}/projects`} data-testid="overview-projects">
            Projects
          </Link>
        </Button>
        <Button variant="ghost" size="sm" asChild>
          <Link href={`/connections/${vm.connectionId}/builder`}>Open Builder</Link>
        </Button>
        <Button variant="ghost" size="sm" asChild>
          <a href="#overview-health-sweep">Run health sweep</a>
        </Button>
      </div>

      <FirstRunCard connectionId={vm.connectionId} modelCount={vm.models.length} />
      <InstanceFingerprintCard connectionId={vm.connectionId} context="overview" />
    </>
  );
}
