"use client";

import Link from "next/link";
import { useState } from "react";
import { api, InstanceFingerprint } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";

export type InstanceFingerprintContext = "overview" | "config" | "develop";

type Props = {
  connectionId: string;
  context?: InstanceFingerprintContext;
};

const COPY: Record<InstanceFingerprintContext, string> = {
  overview:
    "A read-only snapshot of this Odoo database — installed apps, chart of accounts, users, mail, and lock dates. Take one before Job Autopilot or a Config Packet, or when comparing sandbox to a client. It never writes to Odoo.",
  config:
    "You're about to change or replay settings. Fingerprint first so you have a receipt of this database's shape — apps, CoA, users, mail, and locks. Read-only; it does not write to Odoo.",
  develop:
    "Before you promote to a client connection, fingerprint the target so you know which apps, CoA, users, mail servers, and lock dates you're aiming at. Read-only; it does not write to Odoo.",
};

export function InstanceFingerprintCard({
  connectionId,
  context = "overview",
}: Props) {
  const [fp, setFp] = useState<InstanceFingerprint | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      const out = await api.jobAutopilotFingerprint(connectionId);
      setFp(out.fingerprint);
      setMessage(out.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fingerprint failed");
    } finally {
      setBusy(false);
    }
  }

  const mail = fp?.mail;
  const locks = [fp?.period_lock_date, fp?.fiscalyear_lock_date, fp?.tax_lock_date].filter(Boolean);

  return (
    <Card
      className="mt-6 p-5"
      data-testid="instance-fingerprint"
      data-context={context}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold text-ink">Instance fingerprint</h2>
        <Button type="button" size="sm" variant="secondary" disabled={busy} onClick={() => void run()}>
          {busy ? "Reading…" : fp ? "Refresh fingerprint" : "Fingerprint this instance"}
        </Button>
      </div>
      <p className="mt-2 text-sm text-muted">{COPY[context]}</p>
      {error ? <p className="mt-2 text-sm text-danger">{error}</p> : null}
      {fp ? (
        <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted">Major / sha</dt>
            <dd className="font-mono">
              {fp.major ?? "—"} · {fp.sha256}
            </dd>
          </div>
          <div>
            <dt className="text-muted">Installed apps</dt>
            <dd>{fp.modules_installed.length}</dd>
          </div>
          <div>
            <dt className="text-muted">Chart of accounts</dt>
            <dd>{fp.account_code_count} codes</dd>
          </div>
          <div>
            <dt className="text-muted">Users</dt>
            <dd>{fp.user_logins.length} logins</dd>
          </div>
          <div>
            <dt className="text-muted">Mail</dt>
            <dd>
              {mail?.ok
                ? `${mail.smtp_servers} SMTP server(s)`
                : mail?.warnings?.[0] || "No outgoing mail server"}
            </dd>
          </div>
          <div>
            <dt className="text-muted">Lock dates</dt>
            <dd>{locks.length ? locks.join(" · ") : "none"}</dd>
          </div>
        </dl>
      ) : (
        <p className="mt-2 text-sm text-muted">{message || "Not fingerprinted yet."}</p>
      )}
      <p className="mt-3 text-sm">
        <Link href={`/connections/${connectionId}/job`} className="text-accent hover:underline">
          Job Autopilot → Config Packet
        </Link>
      </p>
    </Card>
  );
}
