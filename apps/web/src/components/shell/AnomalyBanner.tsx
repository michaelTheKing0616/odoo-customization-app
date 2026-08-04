"use client";

import Link from "next/link";
import { Callout } from "@/components/ui/Callout";
import type { Connection } from "@/lib/api";

type Props = {
  connection: Connection;
};

/** TRUST-3 — surface auto-pause when anomaly guard trips writes_paused. */
export function AnomalyBanner({ connection }: Props) {
  if (!connection.writes_paused) return null;
  return (
    <Callout variant="danger" title="Writes paused — anomaly guard" testId="anomaly-banner">
      Mutations on this connection are blocked after an hourly mutation budget trip. Review the{" "}
      <Link href={`/connections/${connection.id}/journal`} className="underline">
        journal
      </Link>{" "}
      then unpause from connection settings when safe.
    </Callout>
  );
}
