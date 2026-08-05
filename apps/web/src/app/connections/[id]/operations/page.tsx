"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Card, PageHeader } from "@/components/ui/layout-primitives";
import {
  IconBulk,
  IconCron,
  IconHousekeeping,
  IconPowerOps,
  IconReminders,
  IconScriptRunner,
} from "@/components/ui/icons";

const TOOLS = [
  {
    id: "bulk-suite",
    label: "Bulk Suite",
    href: "bulk-suite",
    icon: IconBulk,
    description: "Mass edit, dedupe, transitions, and bulk messaging across many records.",
  },
  {
    id: "power-ops",
    label: "Power Ops",
    href: "power-ops",
    icon: IconPowerOps,
    description: "Run predefined recipes for common multi-record operations.",
  },
  {
    id: "cron-manager",
    label: "Cron Manager",
    href: "cron-manager",
    icon: IconCron,
    description: "Inspect and manage scheduled jobs on this connection.",
  },
  {
    id: "housekeeping",
    label: "Housekeeping",
    href: "housekeeping",
    icon: IconHousekeeping,
    description: "Scan attachments, recompute stored fields, and clean orphans.",
  },
  {
    id: "reminders",
    label: "Reminders",
    href: "reminders",
    icon: IconReminders,
    description: "Schedule follow-up reminders tied to records.",
  },
  {
    id: "script-runner",
    label: "Script Runner",
    href: "script-runner",
    icon: IconScriptRunner,
    description: "Run ad-hoc Python in an isolated subprocess (developer tool).",
  },
] as const;

export default function OperationsHubPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;
  const base = `/connections/${connectionId}`;

  return (
    <div className="mx-auto max-w-5xl" data-testid="operations-hub">
      <PageHeader
        title="Operations"
        description="Bulk tools, cron, housekeeping, and scripts — all routes stay the same."
      />
      <div className="grid gap-4 sm:grid-cols-2">
        {TOOLS.map((tool) => {
          const Icon = tool.icon;
          return (
            <Link key={tool.id} href={`${base}/${tool.href}`}>
              <Card className="h-full p-4 transition-colors hover:border-accent/40">
                <div className="flex items-start gap-3">
                  <Icon className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
                  <div>
                    <h2 className="font-semibold text-ink">{tool.label}</h2>
                    <p className="mt-1 text-sm text-muted">{tool.description}</p>
                  </div>
                </div>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
