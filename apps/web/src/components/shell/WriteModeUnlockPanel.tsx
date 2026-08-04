"use client";

import { useState } from "react";
import { api, Connection } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { WriteModeBadge } from "@/components/shell/WriteModeBadge";

type Props = {
  connection: Connection;
  onUpdated: (connection: Connection) => void;
};

export function WriteModeUnlockPanel({ connection, onUpdated }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function unlock(mode: "standard" | "production") {
    setBusy(true);
    setError(null);
    try {
      const updated = await api.updateConnectionWriteMode(connection.id, mode);
      onUpdated(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update write mode");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Callout
      variant={connection.write_mode === "observer" ? "info" : "warning"}
      title={`Write mode — ${connection.write_mode}`}
      testId="write-mode-panel"
    >
      <div className="mb-2">
        <WriteModeBadge mode={connection.write_mode} />
      </div>
      {connection.write_mode === "observer" ? (
        <p className="text-sm">
          This connection is read-only. Browse, analyze, and use Expert freely — mutating actions
          stay disabled until a workspace admin unlocks write mode.
        </p>
      ) : (
        <p className="text-sm">
          Write mode is enabled. Mutations use snapshots and confirm gates where configured.
        </p>
      )}
      {error ? <ErrorNotice message={error} className="mt-3" /> : null}
      <div className="mt-3 flex flex-wrap gap-2">
        {connection.write_mode === "observer" ? (
          <Button
            type="button"
            size="sm"
            disabled={busy}
            onClick={() => unlock("standard")}
            data-testid="unlock-standard-write-mode"
          >
            Enable standard write mode
          </Button>
        ) : null}
        {connection.write_mode !== "production" ? (
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={busy}
            onClick={() => unlock("production")}
            data-testid="unlock-production-write-mode"
          >
            Request production mode
          </Button>
        ) : null}
      </div>
    </Callout>
  );
}
