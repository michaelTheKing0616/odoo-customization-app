"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ExpertOverviewCard } from "@/components/expert/ExpertOverviewCard";
import { PageHeader } from "@/components/ui/layout-primitives";
import { api, type Connection } from "@/lib/api";
import { expertHeaderDescription } from "@/lib/expert-journey";

/**
 * Dedicated Expert destination (Week 6).
 * Drawer/panel via openExpert stays for in-context asks; this route is the
 * navigable home — not a competing AI Studio start door (nav sidebar:false).
 */
export default function ExpertDestinationPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;
  const [connection, setConnection] = useState<Connection | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getConnection(connectionId)
      .then((row) => {
        if (!cancelled) setConnection(row);
      })
      .catch(() => {
        if (!cancelled) setConnection(null);
      });
    return () => {
      cancelled = true;
    };
  }, [connectionId]);

  return (
    <div className="mx-auto max-w-3xl" data-testid="expert-destination">
      <PageHeader
        title="Odoo Expert"
        description={expertHeaderDescription(connection?.name)}
        actions={
          <Link
            href={`/connections/${connectionId}`}
            className="text-sm text-muted hover:text-ink"
          >
            Overview
          </Link>
        }
      />
      <div className="studio-refinement">
        <ExpertOverviewCard
          connectionId={connectionId}
          connectionName={connection?.name}
        />
      </div>
    </div>
  );
}
