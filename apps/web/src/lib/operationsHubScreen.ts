/**
 * UI-S-29 Operations hub screen logic and copy.
 * Pure helpers. No React. Hub with no fake metrics.
 * One teal primary: Open Bulk Suite (featured next). Tool cards stay quiet links.
 */

export const PAGE_TITLE = "Operations";
export const PAGE_DESCRIPTION =
  "Pick a live-ops tool for this connection. Bulk and recipe tools test run before write. Cron, housekeeping, reminders, and scripts stay on their own routes.";
export const PRIMARY_CTA = "Open Bulk Suite";
export const FEATURED_TOOL_ID = "bulk-suite" as const;

export type OpsHubGuide = { title: string; why: string; next: string };

export type OpsHubToolId =
  | "live-demo-copilot"
  | "bulk-suite"
  | "power-ops"
  | "cron-manager"
  | "housekeeping"
  | "reminders"
  | "script-runner";

export type OpsHubGroupId = "present" | "write" | "maintain" | "developer";

export type OpsHubTool = {
  id: OpsHubToolId;
  label: string;
  href: string;
  group: OpsHubGroupId;
  description: string;
  /** Quiet risk hint under the card; not a metric. */
  hint: string;
};

export type OpsHubGroup = {
  id: OpsHubGroupId;
  label: string;
  blurb: string;
};

export const OPS_HUB_GROUPS: readonly OpsHubGroup[] = [
  {
    id: "present",
    label: "Present",
    blurb: "Live demos without leaving the meeting.",
  },
  {
    id: "write",
    label: "Write at scale",
    blurb: "Test run first. Writes need the risk phrase on the tool page.",
  },
  {
    id: "maintain",
    label: "Maintain",
    blurb: "Schedules, cleanup, and follow-ups on this connection.",
  },
  {
    id: "developer",
    label: "Developer",
    blurb: "Isolated scripts. Sandbox warning stays on that page.",
  },
] as const;

export const OPS_HUB_TOOLS: readonly OpsHubTool[] = [
  {
    id: "live-demo-copilot",
    label: "Live Demo Co-Pilot",
    href: "live-demo-copilot",
    group: "present",
    description:
      "Consent-first presenter overlay for live demos. Join, capture, and coach without leaving the meeting.",
    hint: "Consent before launch",
  },
  {
    id: "bulk-suite",
    label: "Bulk Suite",
    href: "bulk-suite",
    group: "write",
    description: "Mass edit, dedupe, transitions, and bulk messaging across many records.",
    hint: "Test run before Run",
  },
  {
    id: "power-ops",
    label: "Power Ops",
    href: "power-ops",
    group: "write",
    description: "Run predefined recipes for common multi-record operations.",
    hint: "Test run before Run recipe",
  },
  {
    id: "cron-manager",
    label: "Cron Manager",
    href: "cron-manager",
    group: "maintain",
    description: "Inspect and manage scheduled jobs on this connection.",
    hint: "Next-run in connection timezone",
  },
  {
    id: "housekeeping",
    label: "Housekeeping",
    href: "housekeeping",
    group: "maintain",
    description: "Scan attachments, recompute stored fields, and clean orphans.",
    hint: "Snapshot before Clean",
  },
  {
    id: "reminders",
    label: "Reminders",
    href: "reminders",
    group: "maintain",
    description: "Schedule follow-up reminders tied to records.",
    hint: "Create on this connection",
  },
  {
    id: "script-runner",
    label: "Script Runner",
    href: "script-runner",
    group: "developer",
    description: "Run ad-hoc Python in an isolated subprocess (developer tool).",
    hint: "Sandbox warning stays",
  },
] as const;

/** Strip em / en dashes from UI copy (playbook §0 law 9). */
export function sanitizeOpsHubCopy(text: string): string {
  return text.replace(/[—–]/g, "-");
}

export function pickToolGuide(): OpsHubGuide {
  return {
    title: "Pick a tool for this connection",
    why: "Live-ops routes only. No invented counts. Each tool owns its own test run and write path.",
    next: "Start with Bulk Suite for multi-record writes, or open the tool that matches the job.",
  };
}

export function opsHubHonestyGuide(): OpsHubGuide {
  return {
    title: "Ops tools can write to Odoo",
    why: "Bulk Suite, Power Ops, Cron Manager, Housekeeping, and Script Runner can change live data. Live Demo Co-Pilot needs consent before capture. Reminders schedule follow-ups on records.",
    next: "Use test run where the tool offers it. Read blast radius and confirm with the risk phrase only when the preview looks right.",
  };
}

export function toolsForGroup(groupId: OpsHubGroupId): OpsHubTool[] {
  return OPS_HUB_TOOLS.filter((t) => t.group === groupId);
}

export function featuredTool(): OpsHubTool {
  const tool = OPS_HUB_TOOLS.find((t) => t.id === FEATURED_TOOL_ID);
  if (!tool) throw new Error("featured Operations tool missing");
  return tool;
}

export function opsHubHasEmDash(text: string): boolean {
  return /[—–]/.test(text);
}
