"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import type { StudioAppDesign } from "@/lib/studio-session";
import { BuildCustomCodeButton } from "./AppDesignPanel";

type Batch = {
  pieces?: { label: string }[];
  online_blocked?: boolean | string;
  note?: string;
  session_id?: string;
};

/** One entry into the Option A lane for a designed app's Python pieces. */
export function StudioCustomCodeEntry({
  connectionId,
  sessionId,
  artifact,
}: {
  connectionId: string;
  sessionId: string;
  artifact: Record<string, unknown> | null | undefined;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const batch = (artifact?._option_a_batch ?? null) as Batch | null;
  const design = (artifact?._app_design ?? null) as StudioAppDesign | null;
  if (!batch || !design?.python_needed?.length) return null;
  const view: StudioAppDesign = batch.online_blocked === true || batch.online_blocked === "true"
    ? {
        ...design,
        python_needed: design.python_needed.map((p) => ({ ...p, online_blocked: true, lane_note: batch.note || p.lane_note })),
      }
    : design;

  async function build() {
    setBusy(true);
    setError(null);
    try {
      const out = await api.startOptionABatch(sessionId);
      router.push(`/connections/${connectionId}/studio?session=${out.session_id}&phase=review`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't start the custom code build.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card clarify-card" data-testid="studio-custom-code-entry">
      <h3 className="clarify-question">Custom code</h3>
      <p className="clarify-help">
        {(batch.pieces || []).map((p) => p.label).join(", ")}. These run as one module: build and test
        it, then publish.
      </p>
      <BuildCustomCodeButton design={view} busy={busy} onBuild={() => void build()} />
      {error ? <p className="clarify-help" role="alert">{error}</p> : null}
    </section>
  );
}
