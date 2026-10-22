/**
 * UI-S-51 Fleet command (/command) screen logic and copy.
 * Pure helpers. No React. Workspace-wide counts; one teal primary: Open a client.
 * Honesty: tiles aggregate every connection; this page never writes across the fleet.
 */

export const PAGE_TITLE = "Fleet";
export const PAGE_DESCRIPTION =
  "Workspace health across every Odoo connection. Each tile loads on its own.";
export const PRIMARY_CTA = "Open a client";
export const EMPTY_CTA = "Connect Odoo";
export const RETRY_CTA = "Retry tile";
export const REFRESH_CTA = "Refresh clients";

export const FLEET_STEPS = ["Fleet", "Inspect", "Open client"] as const;
export type FleetStepLabel = (typeof FLEET_STEPS)[number];
export type FleetStepIndex = 1 | 2 | 3;

export type FleetGuide = { title: string; why: string; next: string };

export type FleetTileId =
  | "clients"
  | "pending-approvals"
  | "failed-jobs"
  | "drift";

export type FleetTileSpec = {
  id: FleetTileId;
  title: string;
  detail: string;
  href: string;
  countUrl: string;
  emptyLabel: string;
};

export const FLEET_TILES: readonly FleetTileSpec[] = [
  {
    id: "clients",
    title: "Clients",
    detail: "Odoo connections in this workspace.",
    href: "/connect",
    countUrl: "/api/command/tiles/clients",
    emptyLabel: "none yet",
  },
  {
    id: "pending-approvals",
    title: "Pending approvals",
    detail: "Plan cards waiting on a fingerprint.",
    href: "/approvals",
    countUrl: "/api/command/tiles/pending-approvals",
    emptyLabel: "inbox clear",
  },
  {
    id: "failed-jobs",
    title: "Failed jobs",
    detail: "Background runs that stopped with an error.",
    href: "/connect",
    countUrl: "/api/command/tiles/failed-jobs",
    emptyLabel: "none recent",
  },
  {
    id: "drift",
    title: "Drift",
    detail: "Connections where Odoo upgraded since the last verify.",
    href: "/connect",
    countUrl: "/api/command/tiles/drift",
    emptyLabel: "all current",
  },
] as const;

/** Strip em / en dashes from UI copy (playbook section 0 law 9). */
export function sanitizeFleetCopy(text: string): string {
  return text.replace(/[—–]/g, "-");
}

export function fleetHasEmDash(text: string): boolean {
  return /[—–]/.test(text);
}

export function fleetHonestyGuide(): FleetGuide {
  return {
    title: "Counts span the whole fleet",
    why: "Pending approvals, failed jobs, and drift add up every connection. This page never writes across connections.",
    next: "Open a tile to inspect, then open one client to act.",
  };
}

export function idleFleetGuide(): FleetGuide {
  return {
    title: "Inspect a tile, then open a client",
    why: "Tiles are read-only fleet totals. Acting on an approval, job, or drift item always happens inside one connection.",
    next: "Pick a tile with a non-zero count, or Open a client to choose which Odoo to work in.",
  };
}

export function emptyFleetGuide(): FleetGuide {
  return {
    title: "No clients connected yet",
    why: "Fleet tiles stay at zero until this workspace has at least one Odoo connection.",
    next: "Connect Odoo to add the first client. Approvals, jobs, and drift will appear here after that.",
  };
}

export function partialFleetGuide(failedTileTitle: string): FleetGuide {
  return {
    title: `${failedTileTitle} could not load`,
    why: "Each tile fetches on its own. Sibling counts stay visible so a slow or failing source does not blank the page.",
    next: "Retry the failed tile, or open a client while the rest of the fleet stays on screen.",
  };
}

export function errorFleetGuide(): FleetGuide {
  return {
    title: "Fleet counts could not load",
    why: "The command endpoints did not return usable totals. Auth may be off, or the API may be unreachable.",
    next: "Retry the page, confirm you are signed in as a consultant, then Open a client if you already know which connection to use.",
  };
}

export function loadingFleetGuide(): FleetGuide {
  return {
    title: "Loading fleet tiles",
    why: "Each tile hydrates on its own track. A slow source keeps its skeleton without clearing the others.",
    next: "Wait for counts, or Open a client if you already know where to work.",
  };
}

export function primaryCtaForFleet(clientCount: number | null): string {
  if (clientCount === 0) return EMPTY_CTA;
  return PRIMARY_CTA;
}

export function stepForFleetState(opts: {
  clientCount: number | null;
  hasTileError: boolean;
  loading: boolean;
}): FleetStepIndex {
  if (opts.loading) return 1;
  if (opts.clientCount === 0) return 1;
  if (opts.hasTileError) return 2;
  if ((opts.clientCount ?? 0) > 0) return 2;
  return 1;
}
