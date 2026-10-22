"use client";

import Link from "next/link";
import type { ComponentType } from "react";
import {
  IconBulk,
  IconCron,
  IconHousekeeping,
  IconOdooExpert,
  IconPowerOps,
  IconReminders,
  IconScriptRunner,
} from "@/components/ui/icons";
import {
  FEATURED_TOOL_ID,
  OPS_HUB_GROUPS,
  type OpsHubTool,
  type OpsHubToolId,
  toolsForGroup,
} from "@/lib/operationsHubScreen";

const ICONS: Record<OpsHubToolId, ComponentType<{ className?: string }>> = {
  "live-demo-copilot": IconOdooExpert,
  "bulk-suite": IconBulk,
  "power-ops": IconPowerOps,
  "cron-manager": IconCron,
  housekeeping: IconHousekeeping,
  reminders: IconReminders,
  "script-runner": IconScriptRunner,
};

type OpsHubToolGroupsProps = {
  base: string;
  tools?: readonly OpsHubTool[];
};

export function OpsHubToolGroups({ base, tools }: OpsHubToolGroupsProps) {
  return (
    <div className="oh-groups" data-testid="ops-hub-groups">
      {OPS_HUB_GROUPS.map((group) => {
        const groupTools = tools
          ? tools.filter((t) => t.group === group.id)
          : toolsForGroup(group.id);
        if (groupTools.length === 0) return null;
        return (
          <section
            key={group.id}
            className="oh-group"
            data-group={group.id}
            data-testid={`ops-hub-group-${group.id}`}
            aria-labelledby={`ops-hub-group-${group.id}-label`}
          >
            <div className="oh-group-head">
              <h2 className="oh-group-label" id={`ops-hub-group-${group.id}-label`}>
                {group.label}
              </h2>
              <p className="oh-group-blurb">{group.blurb}</p>
            </div>
            <div className="oh-tool-grid">
              {groupTools.map((tool) => {
                const Icon = ICONS[tool.id];
                const featured = tool.id === FEATURED_TOOL_ID;
                return (
                  <Link
                    key={tool.id}
                    href={`${base}/${tool.href}`}
                    className="oh-tool"
                    data-testid={`ops-hub-tool-${tool.id}`}
                    data-featured={featured ? "true" : "false"}
                  >
                    <span className="oh-tool-icon" aria-hidden>
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="oh-tool-body">
                      <p className="oh-tool-name">{tool.label}</p>
                      <p className="oh-tool-desc">{tool.description}</p>
                      <p className="oh-tool-hint">{tool.hint}</p>
                    </span>
                    <span className="oh-tool-open" aria-hidden>
                      Open
                    </span>
                  </Link>
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
