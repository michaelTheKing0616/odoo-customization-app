"use client";

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
