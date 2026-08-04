"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Connection } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { DialogPanel } from "@/components/ui/Dialog";

const STORAGE_PREFIX = "first-write-ack:";

type Props = {
  connection: Connection | null;
};

export function FirstWriteInterstitial({ connection }: Props) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!connection || connection.write_mode === "observer") return;
    const key = `${STORAGE_PREFIX}${connection.id}`;
    if (typeof window !== "undefined" && localStorage.getItem(key) === "1") return;

    let cancelled = false;
    api
      .getProductionReadiness(connection.id)
      .then((report) => {
        if (cancelled || report.first_write_acknowledged) {
          localStorage.setItem(key, "1");
          return;
        }
        setOpen(true);
      })
      .catch(() => {
        /* still show interstitial on first mutating visit */
        setOpen(true);
      });
    return () => {
      cancelled = true;
    };
  }, [connection]);

  async function dismiss() {
    if (!connection) return;
    const key = `${STORAGE_PREFIX}${connection.id}`;
    localStorage.setItem(key, "1");
    try {
      await api.ackProductionFirstWrite(connection.id);
    } catch {
      /* local dismiss still applies */
    }
    setOpen(false);
  }

  if (!connection) return null;

  return (
    <DialogPanel
      open={open}
      onOpenChange={setOpen}
      title="Before your first write on this connection"
      description="A snapshot is taken before many risky changes. The journal records mutating API calls. You can pause writes or rollback snapshots where reversible."
      testId="first-write-interstitial"
      footer={
        <>
          <Button type="button" variant="secondary" asChild>
            <Link href="/settings/trust-safety">Trust & safety</Link>
          </Button>
          <Button type="button" onClick={() => void dismiss()} data-testid="first-write-dismiss">
            I understand — continue
          </Button>
        </>
      }
    >
      <ul className="list-disc space-y-2 pl-5 text-sm text-muted">
        <li>Mutations run as your Odoo user — the app cannot exceed that user&apos;s rights.</li>
        <li>Not everything is fully reversible — see the safety contract for the verified table.</li>
        <li>Use writes_paused on the connection or workspace to stop mutations immediately.</li>
      </ul>
    </DialogPanel>
  );
}
