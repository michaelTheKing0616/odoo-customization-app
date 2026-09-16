"use client";

import { useEffect, useState } from "react";
import { api, type EePlaybook } from "@/lib/api";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { InlineWait } from "@/components/studio/StudioBusyLabel";
import { formatFetchError } from "@/lib/format-fetch-error";

type Props = {
  connectionId: string;
  className?: string;
};

export function EePlaybooksPanel({ connectionId, className = "" }: Props) {
  const [rows, setRows] = useState<EePlaybook[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .listEePlaybooks(connectionId)
      .then((list) => {
        if (!cancelled) {
          setRows(list);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const raw = err instanceof Error ? err.message : "Failed to load EE playbooks";
          setError(formatFetchError(raw));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [connectionId, reloadKey]);

  return (
    <div className={`text-sm ${className}`} data-testid="ee-playbooks-panel">
      <p className="text-xs font-medium text-muted">Enterprise playbooks (RPC)</p>
      <p className="mt-0.5 text-ui-meta text-muted">
        Greyed out when the required module is not installed. Public ORM only — never
        Studio source.
      </p>
      {loading && <InlineWait />}
      {error ? (
        <ErrorNotice
          message={error}
          showDiagnose={false}
          onRetry={() => setReloadKey((k) => k + 1)}
          className="mt-2"
        />
      ) : null}
      {!loading && !error && (
        <ul className="mt-2 space-y-1">
          {rows.map((pb) => (
            <li
              key={pb.id}
              data-testid={`ee-playbook-${pb.id}`}
              data-available={pb.available ? "true" : "false"}
              className={
                pb.available
                  ? "border border-border-subtle bg-surface-muted px-2 py-1.5 text-xs text-muted"
                  : "border border-border-subtle bg-surface px-2 py-1.5 text-xs text-muted opacity-60"
              }
              aria-disabled={!pb.available}
            >
              <span className="font-medium">{pb.name}</span>
              {!pb.available && (
                <span className="ml-2 text-ui-meta uppercase tracking-wide">Unavailable</span>
              )}
              {pb.warn_only && pb.available && (
                <span className="ml-2 text-ui-meta text-warning">Warn only</span>
              )}
              <span className="mt-0.5 block text-ui-meta text-muted">{pb.reason}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
