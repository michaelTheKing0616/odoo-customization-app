"use client";

import { request } from "@/lib/api/client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/layout-primitives";
import {
  RETRY_CTA,
  sanitizeFleetCopy,
  type FleetTileSpec,
} from "@/lib/fleetCommandScreen";

export type CommandTileSpec = FleetTileSpec;

type TileState =
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | { phase: "ready"; count: number };

/** Optional harness override so vision / e2e can freeze a tile without network. */
export type CommandTileHarness =
  | { phase: "loading" }
  | { phase: "error"; message?: string }
  | { phase: "ready"; count: number };

/** Through the shared API helper, so API-key sessions send their key too. */
async function fetchCount(url: string): Promise<number> {
  const body = await request<{ count: number }>(url);
  if (typeof body?.count !== "number") throw new Error("count_failed");
  return body.count;
}

function chipFor(tile: CommandTileSpec, count: number | null, phase: TileState["phase"]): string {
  if (phase === "loading") return "Counting";
  if (phase === "error") return "Retry";
  if (count === 0) return "Clear";
  if (tile.id === "clients") return "Connected";
  if (tile.id === "pending-approvals") return "Waiting";
  if (tile.id === "failed-jobs") return "Needs care";
  if (tile.id === "drift") return "Changed";
  return "Open";
}

export function CommandCenterTile({
  tile,
  harness,
  onPhaseChange,
}: {
  tile: CommandTileSpec;
  harness?: CommandTileHarness;
  onPhaseChange?: (tileId: string, phase: TileState["phase"]) => void;
}) {
  const [state, setState] = useState<TileState>(() =>
    harness
      ? harness.phase === "error"
        ? {
            phase: "error",
            message:
              harness.message ??
              `${tile.title} could not be loaded. Retry keeps the rest of the page visible.`,
          }
        : harness.phase === "ready"
          ? { phase: "ready", count: harness.count }
          : { phase: "loading" }
      : { phase: "loading" },
  );

  const load = useCallback(async () => {
    if (harness) return;
    setState({ phase: "loading" });
    onPhaseChange?.(tile.id, "loading");
    try {
      const count = await fetchCount(tile.countUrl);
      setState({ phase: "ready", count });
      onPhaseChange?.(tile.id, "ready");
    } catch {
      setState({
        phase: "error",
        message: `${tile.title} could not be loaded. Retry keeps the rest of the page visible.`,
      });
      onPhaseChange?.(tile.id, "error");
    }
  }, [harness, onPhaseChange, tile.countUrl, tile.id, tile.title]);

  useEffect(() => {
    if (harness) {
      onPhaseChange?.(tile.id, harness.phase);
      return;
    }
    void load();
  }, [harness, load, onPhaseChange, tile.id]);

  const count = state.phase === "ready" ? state.count : null;
  const hot = state.phase === "ready" && (count ?? 0) > 0;

  return (
    <li>
      <Link
        href={tile.href}
        className="fc-tile"
        data-testid={`command-tile-${tile.id}`}
        data-phase={state.phase}
        data-hot={hot ? "true" : "false"}
      >
        <div className="fc-tile-head">
          <span className="fc-tile-title">{sanitizeFleetCopy(tile.title)}</span>
          <span className="fc-tile-chip" aria-hidden>
            {chipFor(tile, count, state.phase)}
          </span>
        </div>
        <span className="fc-tile-detail">{sanitizeFleetCopy(tile.detail)}</span>
        <div className="fc-tile-foot" aria-live="polite">
          {state.phase === "loading" ? (
            <div data-testid={`command-tile-${tile.id}-skeleton`}>
              <Skeleton className="h-9 w-20" />
            </div>
          ) : null}
          {state.phase === "error" ? (
            <div
              className="fc-tile-error"
              onClick={(event) => event.preventDefault()}
              onKeyDown={(event) => event.stopPropagation()}
            >
              <p role="alert">{sanitizeFleetCopy(state.message)}</p>
              {!harness ? (
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={(event) => {
                    event.preventDefault();
                    void load();
                  }}
                  data-testid={`command-tile-${tile.id}-retry`}
                >
                  {RETRY_CTA}
                </Button>
              ) : null}
            </div>
          ) : null}
          {state.phase === "ready" ? (
            <>
              <p
                className="fc-tile-count"
                data-testid={`command-tile-${tile.id}-count`}
              >
                {count}
              </p>
              {count === 0 ? (
                <span className="fc-tile-empty">{sanitizeFleetCopy(tile.emptyLabel)}</span>
              ) : null}
            </>
          ) : null}
        </div>
      </Link>
    </li>
  );
}
