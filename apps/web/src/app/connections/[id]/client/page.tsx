"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ConnectionClientPanel } from "@/components/connection-client/ConnectionClientPanel";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/layout-primitives";

export default function ConnectionClientPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  return (
    <div className="mx-auto max-w-5xl px-1" data-testid="connection-client-page">
      <PageHeader
        title="Client"
        description="One connection — open change-sets, last snapshot, and bot roster status. Each block loads on its own so a slow source does not blank the page."
        actions={
          <Button variant="ghost" size="sm" asChild>
            <Link href={`/connections/${connectionId}`}>Back to overview</Link>
          </Button>
        }
      />
      <ConnectionClientPanel connectionId={connectionId} />
    </div>
  );
}
