"use client";

/** BV-UI-WIRE: loads one verify run and shows it in the BV-UI evidence viewer. */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { botVerifyApi, type VerifyRun } from "@/lib/api/botVerify";
import { EvidenceViewer } from "./EvidenceViewer";

export type VerifyRunPanelProps = { connectionId: string; runId: string };

type Load =
  | { kind: "loading" }
  | { kind: "ready"; run: VerifyRun }
  | { kind: "empty" }
  | { kind: "denied"; group: string }
  | { kind: "error"; copy: string };

const COPY_FAILED = "We couldn't load this check just now. Your Odoo data is unchanged.";
const COPY_ACCESS = "You don't have access to this check. Ask a workspace admin for access.";

function toLoad(err: unknown): Load {
  const e = err as { status?: number; detail?: unknown };
  if (e?.status === 404) return { kind: "empty" };
  if (e?.status === 403) {
    const inner = (e.detail as { detail?: { group?: unknown } } | null)?.detail;
    const group = typeof inner?.group === "string" ? inner.group : "";
    return group ? { kind: "denied", group } : { kind: "error", copy: COPY_ACCESS };
  }
  return { kind: "error", copy: COPY_FAILED };
}

export function VerifyRunPanel({ connectionId, runId }: VerifyRunPanelProps) {
  const [load, setLoad] = useState<Load>({ kind: "loading" });
  const seq = useRef(0);

  const fetchRun = useCallback(() => {
    const mine = ++seq.current;
    setLoad({ kind: "loading" });
    botVerifyApi.getVerifyRun(connectionId, runId).then(
      (run) => {
        if (seq.current === mine) setLoad({ kind: "ready", run });
      },
      (err: unknown) => {
        if (seq.current === mine) setLoad(toLoad(err));
      },
    );
  }, [connectionId, runId]);

  useEffect(() => {
    fetchRun();
    return () => {
      seq.current += 1; // drop late responses after unmount or id change
    };
  }, [fetchRun]);

  const artifactUrl = useCallback(
    (shotId: string) => botVerifyApi.verifyArtifactUrl(connectionId, runId, shotId),
    [connectionId, runId],
  );

  return (
    <EvidenceViewer
      run={load.kind === "ready" ? load.run : null}
      artifactUrl={artifactUrl}
      loading={load.kind === "loading"}
      error={load.kind === "error"}
      errorCopy={load.kind === "error" ? load.copy : undefined}
      onRetry={load.kind === "error" ? fetchRun : undefined}
      denied={load.kind === "denied" ? { group: load.group } : null}
    />
  );
}
