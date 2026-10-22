"use client";

import { RelativeTime } from "@/components/ui/craft";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { api, ConnectionGrantRow } from "@/lib/api";
import { reportApiError } from "@/lib/api-error";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { DialogPanel } from "@/components/ui/Dialog";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Card, EmptyState, Skeleton } from "@/components/ui/layout-primitives";
import { StudioBusyLabel } from "@/components/studio/StudioBusyLabel";
import { IconUsers } from "@/components/ui/icons";

const GRANT_ROLES = [
  { value: "client_approver", label: "Client approver — approve plans for this connection" },
  { value: "client_viewer", label: "Client viewer — read-only on this connection" },
] as const;

type GrantRole = (typeof GRANT_ROLES)[number]["value"];

function roleLabel(role: string): string {
  if (role === "client_approver") return "Client approver";
  if (role === "client_viewer") return "Client viewer";
  return role;
}

type ConnectionTeamGrantsPanelProps = {
  connectionId: string;
  connectionName?: string | null;
};

export function ConnectionTeamGrantsPanel({
  connectionId,
  connectionName,
}: ConnectionTeamGrantsPanelProps) {
  const reduceMotion = useReducedMotion();
  const [grants, setGrants] = useState<ConnectionGrantRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [hydrated, setHydrated] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<GrantRole>("client_approver");
  const [busy, setBusy] = useState(false);
  const [forbidden, setForbidden] = useState(false);
  const [pendingRevoke, setPendingRevoke] = useState<ConnectionGrantRow | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setForbidden(false);
    try {
      const rows = await api.listConnectionGrants(connectionId);
      setGrants(rows);
    } catch (err) {
      const message = reportApiError(err, setError, { fallback: "Could not load client grants" });
      if (/\b403\b/.test(message) || /admin required/i.test(message)) {
        setForbidden(true);
      }
    } finally {
      setLoading(false);
      setHydrated(true);
    }
  }, [connectionId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onGrant(e: FormEvent) {
    e.preventDefault();
    const trimmed = email.trim().toLowerCase();
    if (!trimmed) {
      setFormError("Enter the email of someone who already has an Ingenium login.");
      return;
    }
    setBusy(true);
    setFormError(null);
    setError(null);
    try {
      const created = await api.createConnectionGrant({
        connection_id: connectionId,
        email: trimmed,
        role,
      });
      toast.success("Client access granted", {
        description: `${trimmed} can now access ${connectionName ?? "this connection"} as ${roleLabel(created.role)}.`,
      });
      setEmail("");
      await load();
    } catch (err) {
      reportApiError(err, setFormError, {
        fallback: "Grant failed — check the email and try again.",
        toast: true,
      });
    } finally {
      setBusy(false);
    }
  }

  async function onRevokeConfirm() {
    if (!pendingRevoke) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteConnectionGrant(pendingRevoke.id);
      toast.success("Access revoked", {
        description: `${pendingRevoke.email} no longer has client access to this connection.`,
      });
      setPendingRevoke(null);
      await load();
    } catch (err) {
      reportApiError(err, setError, { fallback: "Revoke failed", toast: true });
    } finally {
      setBusy(false);
    }
  }

  const listMotion = reduceMotion
    ? {}
    : {
        initial: { opacity: 0, y: 4 },
        animate: { opacity: 1, y: 0 },
        exit: { opacity: 0, y: -4 },
        transition: { duration: 0.18, ease: "easeOut" as const },
      };

  return (
    <section className="space-y-4" data-testid="connection-team-grants">
      <div>
        <h2 className="text-balance text-sm font-semibold text-ink">Client access grants</h2>
        <p className="mt-1 text-pretty text-xs text-muted">
          Give a client approver or viewer access to{" "}
          <span className="font-medium text-ink">{connectionName ?? "this connection"}</span> only.
          This is not a workspace role — they will not see your other connections.
        </p>
      </div>

      {forbidden ? (
        <Callout variant="warning" title="Admin only">
          Only a workspace admin can grant or revoke client access. Sign in with an owner or admin
          account to manage who can approve on this connection.
        </Callout>
      ) : null}

      {error && !forbidden ? (
        <ErrorNotice message={error} onRetry={() => void load()} />
      ) : null}

      {!forbidden ? (
        <Card className="space-y-3 p-4">
          <form onSubmit={onGrant} className="space-y-3" data-testid="connection-grant-form">
            <Input
              label="Client email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                setFormError(null);
              }}
              placeholder="client@company.com"
              hint="They must already have an Ingenium account before you can grant access."
              error={formError ?? undefined}
              disabled={busy}
              data-testid="connection-grant-email"
            />
            <Select
              label="Access level"
              options={GRANT_ROLES.map((r) => ({ value: r.value, label: r.label }))}
              value={role}
              onChange={(e) => setRole(e.target.value as GrantRole)}
              disabled={busy}
              data-testid="connection-grant-role"
            />
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="submit"
                variant="primary"
                size="sm"
                disabled={busy || !hydrated}
                data-testid="connection-grant-submit"
              >
                {busy ? <StudioBusyLabel>Granting…</StudioBusyLabel> : "Grant access"}
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      <div className="space-y-2">
        <h3 className="text-xs font-medium uppercase tracking-normal text-muted">Active grants</h3>
        {loading && !hydrated ? (
          <div className="space-y-2" data-testid="connection-grants-loading">
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        ) : forbidden ? null : grants.length === 0 ? (
          <EmptyState
            icon={<IconUsers className="h-5 w-5" />}
            title="No client grants yet"
            description="When you grant access, the person can open this connection’s approval inbox only — not the rest of your workspace."
          />
        ) : (
          <ul className="space-y-2" data-testid="connection-grants-list">
            <AnimatePresence initial={false}>
              {grants.map((row) => (
                <motion.li key={row.id} {...listMotion} layout={false}>
                  <Card className="flex flex-wrap items-center justify-between gap-3 p-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-ink">{row.email}</p>
                      <p className="mt-0.5 text-xs text-muted tabular-nums">
                        Granted {row.created_at ? <RelativeTime value={row.created_at} /> : "—"}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={row.role === "client_approver" ? "info" : "default"}>
                        {roleLabel(row.role)}
                      </Badge>
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        disabled={busy}
                        data-testid={`connection-grant-revoke-${row.id}`}
                        onClick={() => setPendingRevoke(row)}
                      >
                        Revoke
                      </Button>
                    </div>
                  </Card>
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>
        )}
      </div>

      <DialogPanel
        open={pendingRevoke != null}
        onOpenChange={(open) => {
          if (!open && !busy) setPendingRevoke(null);
        }}
        title="Revoke client access?"
        description={
          pendingRevoke
            ? `${pendingRevoke.email} will lose access to this connection’s approval inbox immediately. Their Ingenium login stays active for any other grants they may have.`
            : undefined
        }
        testId="connection-grant-revoke-dialog"
        dataRiskLevel="standard"
        footer={
          <>
            <Button
              type="button"
              variant="secondary"
              size="md"
              disabled={busy}
              onClick={() => setPendingRevoke(null)}
            >
              Keep access
            </Button>
            <Button
              type="button"
              variant="primary"
              size="md"
              className="bg-danger hover:bg-danger/90"
              disabled={busy}
              data-testid="connection-grant-revoke-confirm"
              onClick={() => void onRevokeConfirm()}
            >
              {busy ? <StudioBusyLabel>Revoking…</StudioBusyLabel> : "Revoke access"}
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted">
          This writes a revoke entry to the auth audit log. You can grant them again later if needed.
        </p>
      </DialogPanel>
    </section>
  );
}
