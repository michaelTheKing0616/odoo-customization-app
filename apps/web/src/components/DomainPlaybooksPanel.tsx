"use client";

import { useEffect, useState } from "react";
import { api, type DomainPlaybook } from "@/lib/api";

type Props = {
  connectionId: string;
  className?: string;
};

export function DomainPlaybooksPanel({ connectionId, className = "" }: Props) {
  const [rows, setRows] = useState<DomainPlaybook[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .listDomainPlaybooks(connectionId)
      .then((list) => {
        if (!cancelled) {
          setRows(list);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load domain playbooks");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [connectionId]);

  return (
    <div className={`text-sm ${className}`} data-testid="domain-playbooks-panel">
      <p className="text-xs font-medium text-[#a8909e]">Domain playbooks (CRM / Project / Sale)</p>
      <p className="mt-0.5 text-[11px] text-[#6b5a66]">
        Greyed out when the required module is not installed. List/read only via public ORM.
      </p>
      {loading && <p className="mt-2 text-xs text-muted">Loading…</p>}
      {error && <p className="mt-2 text-xs text-[#e8a0a0]">{error}</p>}
      {!loading && !error && (
        <ul className="mt-2 space-y-1">
          {rows.map((pb) => (
            <li
              key={pb.id}
              data-testid={`domain-playbook-${pb.id}`}
              data-available={pb.available ? "true" : "false"}
              className={
                pb.available
                  ? "border border-border-subtle bg-[#120e14] px-2 py-1.5 text-xs text-muted"
                  : "border border-[#1a2a24] bg-surface px-2 py-1.5 text-xs text-[#6b5a66] opacity-60"
              }
              aria-disabled={!pb.available}
            >
              <span className="font-medium">{pb.name}</span>
              {!pb.available && (
                <span className="ml-2 text-[10px] uppercase tracking-wide">Unavailable</span>
              )}
              <span className="mt-0.5 block text-[11px] text-muted">{pb.reason}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
