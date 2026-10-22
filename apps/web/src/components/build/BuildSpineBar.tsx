"use client";

import Link from "next/link";
import { useMemo } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import {
  BUILD_SPINE_HONESTY,
  defaultChips,
  resolveBuildModeLocal,
  type BuildMode,
  type BuildSpineChip,
  type BuildSpinePayload,
} from "@/lib/build-spine";
import { stashBuildSpineHandoff, type BuildSpineHandoff } from "@/lib/build-spine-handoff";
import { BuildSpineChips } from "./BuildSpineChips";

type BuildSpineBarProps = {
  connectionId: string;
  activeMode?: BuildMode;
  payload?: BuildSpinePayload | null;
  handoff?: BuildSpineHandoff | null;
  compact?: boolean;
  showSurfaces?: boolean;
};

export function BuildSpineBar({
  connectionId,
  activeMode,
  payload,
  handoff,
  compact,
  showSurfaces = true,
}: BuildSpineBarProps) {
  const mode =
    activeMode ||
    payload?.build_mode ||
    resolveBuildModeLocal({
      capability: handoff?.capability || payload?.capability,
      grain: handoff?.grain || payload?.grain,
      artifact_kind: handoff?.artifact_kind || payload?.artifact_kind,
      delivery_lane: handoff?.delivery_lane || payload?.delivery_lane,
      gold_artifact_id: handoff?.gold_artifact_id || payload?.gold_artifact_id,
    });

  const chips: BuildSpineChip[] = useMemo(() => {
    if (payload?.chips?.length) {
      return payload.chips.map((c) => ({
        ...c,
        active: c.id === mode,
        href: c.href || `/connections/${connectionId}/studio`,
      }));
    }
    return defaultChips(connectionId, mode);
  }, [connectionId, mode, payload]);

  function onSelect(chip: BuildSpineChip) {
    const next: BuildSpineHandoff = {
      version: 1,
      brief: handoff?.brief || payload?.brief || payload?.prompt || "",
      prompt: handoff?.prompt || payload?.prompt || handoff?.brief || "",
      build_mode: chip.id,
      capability: handoff?.capability || payload?.capability,
      grain: handoff?.grain || payload?.grain,
      delivery_lane: handoff?.delivery_lane || payload?.delivery_lane,
      artifact_kind: handoff?.artifact_kind || payload?.artifact_kind,
      prove_status: handoff?.prove_status || payload?.prove_status,
      gold_artifact_id: handoff?.gold_artifact_id || payload?.gold_artifact_id,
      diagnosis: handoff?.diagnosis || payload?.diagnosis || null,
      contract: handoff?.contract || payload?.contract || null,
    };
    stashBuildSpineHandoff(connectionId, next);
  }

  const lane = handoff?.delivery_lane || payload?.delivery_lane;
  const kind = handoff?.artifact_kind || payload?.artifact_kind;

  return (
    <Card
      className={compact ? "p-3" : "p-4"}
      data-testid="build-spine-bar"
      data-build-mode={mode}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
            Build · one entry
          </p>
          {!compact ? (
            <p className="mt-1 text-sm text-muted" data-testid="build-spine-honesty">
              {payload?.honesty || BUILD_SPINE_HONESTY}
            </p>
          ) : null}
        </div>
        {lane || kind ? (
          <p
            className="max-w-xs text-right text-[11px] text-muted"
            data-testid="build-spine-stamps"
          >
            {lane ? <span className="font-mono text-accent">{lane}</span> : null}
            {lane && kind ? " · " : null}
            {kind ? <span className="font-mono">{kind}</span> : null}
          </p>
        ) : null}
      </div>
      <div className="mt-3">
        <BuildSpineChips
          chips={chips}
          connectionId={connectionId}
          onSelect={(chip) => {
            onSelect(chip);
            if (typeof window !== "undefined" && chip.href) {
              window.location.assign(chip.href);
            }
          }}
        />
      </div>
      {showSurfaces ? (
        <div className="job-handoff-bar mt-3" data-testid="build-spine-surfaces">
          <Button asChild variant="ghost" size="sm">
            <Link
              href={`/connections/${connectionId}/studio`}
              onClick={() =>
                stashBuildSpineHandoff(connectionId, {
                  version: 1,
                  brief: handoff?.brief || payload?.brief || "",
                  prompt: handoff?.prompt || payload?.prompt || handoff?.brief || "",
                  build_mode: mode,
                  capability: handoff?.capability || payload?.capability,
                  grain: handoff?.grain || payload?.grain,
                  delivery_lane: lane,
                  artifact_kind: kind,
                  prove_status: handoff?.prove_status || payload?.prove_status,
                  diagnosis: handoff?.diagnosis || payload?.diagnosis || null,
                  contract: handoff?.contract || payload?.contract || null,
                })
              }
            >
              App Studio
            </Link>
          </Button>
          <Button asChild variant="ghost" size="sm">
            <Link href={`/connections/${connectionId}/wizard`}>Draft Studio</Link>
          </Button>
          <Button asChild variant="ghost" size="sm">
            <Link href={`/connections/${connectionId}/job`}>Job Autopilot</Link>
          </Button>
          <Button asChild variant="ghost" size="sm">
            <Link href={`/connections/${connectionId}/designer`}>View Designer</Link>
          </Button>
        </div>
      ) : null}
    </Card>
  );
}
