"use client";

import { dbColour, isTestCopy, testCopyStatus } from "@/components/ui/craft";
import { Badge } from "@/components/ui/Badge";
import type { Connection } from "@/lib/api";

type Props = {
  connection: Connection;
  className?: string;
};

/** Single instance identity cluster: version · edition · hosting · support tag. */
export function InstanceIdentity({ connection, className = "" }: Props) {
  const caps = connection.capabilities;
  const hosting = caps?.hosting_hint?.replace(/_/g, " ");

  return (
    <div
      className={`flex flex-wrap items-center gap-2 ${className}`}
      data-testid="instance-identity"
    >
      <span
        aria-hidden="true"
        className="inline-block h-2 w-2 rounded-full"
        style={{ background: dbColour(connection.id) }}
        data-testid="instance-colour"
      />
      {isTestCopy(connection) ? <Badge variant="warning">{testCopyStatus(connection).certain ? "Test copy" : "Probably a test copy"}</Badge> : null}
      {connection.server_version ? (
        <Badge variant="info">Odoo {connection.server_version}</Badge>
      ) : null}
      {caps?.edition ? <Badge>{caps.edition}</Badge> : null}
      {hosting ? <Badge>{hosting}</Badge> : null}
      {caps ? (
        <Badge variant={caps.ga ? "ga" : "experimental"}>
          {caps.ga ? "GA" : "Experimental"}
        </Badge>
      ) : null}
    </div>
  );
}
