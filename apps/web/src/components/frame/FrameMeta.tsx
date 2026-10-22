"use client";

import { useContext } from "react";
import { QueryClientContext, useQuery } from "@tanstack/react-query";
import { WriteModeBadge } from "@/components/shell/WriteModeBadge";
import { useShellOptional } from "@/context/ShellContext";
import { api } from "@/lib/api";

/**
 * A2 — one page frame. Every page header (PageHeader and the Operate studio chrome) shows the
 * same meta row: which database, its Odoo version, and whether writes are on. Reads the shell's
 * cached connection, so it never adds a request.
 */
export function FrameMeta() {
  const shell = useShellOptional();
  const client = useContext(QueryClientContext);
  // Outside a connection shell (public pages, isolated tests) there is no database to describe.
  if (!shell?.connectionId || !client) return null;
  return <FrameMetaInner id={shell.connectionId} />;
}

function FrameMetaInner({ id }: { id: string }) {
  const q = useQuery({
    queryKey: ["connection", id],
    queryFn: () => api.getConnection(id),
    enabled: Boolean(id),
    retry: false,
    staleTime: 60_000,
  });
  const c = q.data;
  if (!c) return null;
  const major = c.server_version?.match(/(\d+)/)?.[1];
  return (
    <div className="frame-meta" data-testid="frame-meta">
      <span className="frame-db">{c.name}</span>
      {major ? (
        <span className="frame-chip" data-testid="frame-version">
          Odoo {major}
        </span>
      ) : null}
      <span data-testid="frame-writes">
        <WriteModeBadge mode={c.write_mode} />
      </span>
    </div>
  );
}
