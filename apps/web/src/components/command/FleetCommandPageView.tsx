"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { CommandCenterTile, type CommandTileHarness } from "@/components/command/CommandCenterTile";
import { FleetStageRail } from "@/components/command/FleetStageRail";
import { FleetStateGuide } from "@/components/command/FleetStateGuide";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/layout-primitives";
import {
  FLEET_TILES,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  emptyFleetGuide,
  errorFleetGuide,
  fleetHonestyGuide,
  loadingFleetGuide,
  partialFleetGuide,
  primaryCtaForFleet,
  sanitizeFleetCopy,
  stepForFleetState,
  type FleetTileId,
} from "@/lib/fleetCommandScreen";
import "@/components/command/fleet-operate.css";
import { FrameMeta } from "@/components/frame/FrameMeta";

export type FleetHarnessState = "empty" | "idle" | "loading" | "partial" | "error";

export type FleetTileHarnessMap = Partial<Record<FleetTileId, CommandTileHarness>>;

type FleetCommandPageViewProps = {
  /** Gate skeleton before consultant home is ready. */
  gateLoading?: boolean;
  clientCount: number | null;
  clientsHydrated?: boolean;
  /** When true, show page-level error guide instead of tiles. */
  pageError?: boolean;
  harnessState?: FleetHarnessState;
  tileHarness?: FleetTileHarnessMap;
};

const HARNESS_TILES: Record<FleetHarnessState, FleetTileHarnessMap> = {
  empty: {
    clients: { phase: "ready", count: 0 },
    "pending-approvals": { phase: "ready", count: 0 },
    "failed-jobs": { phase: "ready", count: 0 },
    drift: { phase: "ready", count: 0 },
  },
  idle: {
    clients: { phase: "ready", count: 3 },
    "pending-approvals": { phase: "ready", count: 2 },
    "failed-jobs": { phase: "ready", count: 1 },
    drift: { phase: "ready", count: 0 },
  },
  loading: {
    clients: { phase: "loading" },
    "pending-approvals": { phase: "loading" },
    "failed-jobs": { phase: "loading" },
    drift: { phase: "loading" },
  },
  partial: {
    clients: { phase: "ready", count: 3 },
    "pending-approvals": { phase: "ready", count: 0 },
    "failed-jobs": {
      phase: "error",
      message: "Failed jobs could not be loaded. Retry keeps the rest of the page visible.",
    },
    drift: { phase: "ready", count: 1 },
  },
  error: {},
};

function harnessClientCount(state: FleetHarnessState): number | null {
  if (state === "empty") return 0;
  if (state === "loading" || state === "error") return null;
  return 3;
}

export function FleetCommandPageView({
  gateLoading = false,
  clientCount,
  clientsHydrated = true,
  pageError = false,
  harnessState,
  tileHarness,
}: FleetCommandPageViewProps) {
  const resolvedHarness = harnessState ? HARNESS_TILES[harnessState] : tileHarness;
  const resolvedClientCount = harnessState ? harnessClientCount(harnessState) : clientCount;
  const resolvedPageError = harnessState === "error" ? true : pageError;
  const resolvedLoading =
    gateLoading || harnessState === "loading" || (!harnessState && !clientsHydrated && resolvedClientCount === null);

  const [tilePhases, setTilePhases] = useState<Record<string, string>>({});

  const onPhaseChange = useCallback((tileId: string, phase: string) => {
    setTilePhases((prev) => (prev[tileId] === phase ? prev : { ...prev, [tileId]: phase }));
  }, []);

  const hasTileError = useMemo(() => {
    if (harnessState === "partial") return true;
    if (resolvedHarness) {
      return Object.values(resolvedHarness).some((h) => h?.phase === "error");
    }
    return Object.values(tilePhases).some((p) => p === "error");
  }, [harnessState, resolvedHarness, tilePhases]);

  const failedTileTitle = useMemo(() => {
    if (harnessState === "partial") return "Failed jobs";
    if (resolvedHarness) {
      const hit = FLEET_TILES.find((t) => resolvedHarness[t.id]?.phase === "error");
      return hit?.title ?? "A fleet tile";
    }
    const hit = FLEET_TILES.find((t) => tilePhases[t.id] === "error");
    return hit?.title ?? "A fleet tile";
  }, [harnessState, resolvedHarness, tilePhases]);

  const step = stepForFleetState({
    clientCount: resolvedClientCount,
    hasTileError,
    loading: Boolean(resolvedLoading && !resolvedPageError),
  });

  const ctaLabel = primaryCtaForFleet(
    resolvedPageError ? null : resolvedClientCount === 0 ? 0 : resolvedClientCount ?? 1,
  );

  const honesty = fleetHonestyGuide();
  const isEmpty = !resolvedPageError && resolvedClientCount === 0 && clientsHydrated;
  const isLoading =
    !resolvedPageError &&
    resolvedClientCount !== 0 &&
    !hasTileError &&
    resolvedLoading; // harness "loading" is already folded into resolvedLoading above
  const showSituational =
    resolvedPageError || isEmpty || hasTileError || isLoading;

  const mastheadCta = (
    <Button asChild variant="primary" size="sm">
      <Link href="/connect" data-testid="fleet-primary-cta">
        {ctaLabel}
      </Link>
    </Button>
  );

  if (gateLoading && !harnessState) {
    return (
      <div className="fleet-operate" data-testid="command-center-page" data-gate="loading">
        <div className="fc-desk">
          <div className="fc-sheet">
            <header className="fc-masthead studio-bar-dark">
              <div className="fc-mast-copy">
                <Skeleton className="h-7 w-40" />
                <Skeleton className="mt-2 h-4 w-full max-w-md" />
              </div>
            </header>
            <FleetStageRail step={1} />
            <ul className="fc-tile-grid">
              {FLEET_TILES.map((tile) => (
                <li key={tile.id}>
                  <Skeleton
                    className="h-[8.5rem] w-full"
                    data-testid={`command-tile-${tile.id}-skeleton`}
                  />
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="fleet-operate"
      data-testid="command-center-page"
      data-harness-state={harnessState || undefined}
    >
      <div className="fc-desk">
        <article className="fc-sheet">
          <header className="fc-masthead studio-bar-dark">
            <div className="fc-mast-copy">
              <FrameMeta />
              <h1 className="fc-title">{PAGE_TITLE}</h1>
              <p className="fc-lead" data-testid="fleet-idle-guide">
                <span className="fc-lead-title" data-testid="fleet-idle-guide-title">
                  Inspect a tile, then open a client
                </span>
                <span className="fc-lead-body" data-testid="fleet-idle-guide-why">
                  {sanitizeFleetCopy(PAGE_DESCRIPTION)}
                </span>
                <span className="fc-lead-next" data-testid="fleet-idle-guide-next">
                  Pick a tile with a non-zero count, or Open a client to choose which Odoo to work in.
                </span>
              </p>
            </div>
            <div className="fc-mast-actions">{mastheadCta}</div>
          </header>

          <FleetStageRail step={step} />

          {/* Quiet fleet-scope caption (not an amber Callout stack). */}
          <FleetStateGuide
            density="caption"
            tone="neutral"
            testId="fleet-honesty"
            guide={honesty}
          />

          {resolvedPageError ? (
            <FleetStateGuide
              density="callout"
              tone="danger"
              testId="fleet-error-guide"
              live
              guide={errorFleetGuide()}
            />
          ) : null}

          {isEmpty ? (
            <FleetStateGuide
              density="callout"
              tone="accent"
              testId="fleet-empty-guide"
              guide={emptyFleetGuide()}
            />
          ) : null}

          {!resolvedPageError && hasTileError ? (
            <FleetStateGuide
              density="callout"
              tone="warning"
              testId="fleet-partial-guide"
              live
              guide={partialFleetGuide(failedTileTitle)}
            />
          ) : null}

          {isLoading ? (
            <FleetStateGuide
              density="callout"
              tone="neutral"
              testId="fleet-loading-guide"
              guide={loadingFleetGuide()}
            />
          ) : null}

          {!resolvedPageError ? (
            <ul
              className="fc-tile-grid"
              data-testid="fleet-tile-grid"
              data-density={showSituational ? "with-guide" : "command"}
            >
              {FLEET_TILES.map((tile) => (
                <CommandCenterTile
                  key={tile.id}
                  tile={tile}
                  harness={resolvedHarness?.[tile.id]}
                  onPhaseChange={onPhaseChange}
                />
              ))}
            </ul>
          ) : null}
        </article>
      </div>
    </div>
  );
}
