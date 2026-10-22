"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  api,
  ConfirmationRequiredError,
  type Connection,
  type ProcessGateResponse,
  type ProcessRequestRow,
  type ProcessTypeRow,
} from "@/lib/api";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Callout } from "@/components/ui/Callout";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/layout-primitives";
import {
  processEngineLabel,
  processesEmptyGuide,
  approvalsErrorGuide,
} from "@/lib/approvalScreen";
import { ApprovalsStateGuide } from "./ApprovalsStateGuide";

const CONFIRM_PHRASE = "I understand the risks";

export function ApprovalProcessesPanel({
  connectionId,
  connection,
}: {
  connectionId: string;
  connection: Connection | null;
}) {
  const [gate, setGate] = useState<ProcessGateResponse | null>(null);
  const [types, setTypes] = useState<ProcessTypeRow[]>([]);
  const [requests, setRequests] = useState<ProcessRequestRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const [typeId, setTypeId] = useState("");
  const [subject, setSubject] = useState("Purchase request");
  const [amount, setAmount] = useState("1000");
  const [actorUserId, setActorUserId] = useState("2");

  const refresh = useCallback(async () => {
    const [g, t, r] = await Promise.all([
      api.getProcessGate(connectionId),
      api.listProcessTypes(connectionId),
      api.listProcessRequests(connectionId),
    ]);
    setGate(g);
    setTypes(t);
    setRequests(r);
    if (t.length > 0 && !typeId) setTypeId(String(t[0].id));
  }, [connectionId, typeId]);

  useEffect(() => {
    setHydrated(false);
    refresh()
      .catch((err: Error) => setError(err.message))
      .finally(() => setHydrated(true));
  }, [refresh]);

  async function runScaffold(phrase?: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await api.scaffoldApprovalProcesses(connectionId, {
        confirm_advanced: true,
        confirm_phrase: phrase || CONFIRM_PHRASE,
      });
      setNotice(res.message);
      setConfirmOpen(false);
      await refresh();
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Scaffold failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function createRequest() {
    if (!typeId) {
      setError("Select an approval type");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.createProcessRequest(connectionId, {
        type_id: Number(typeId),
        subject,
        amount: Number(amount) || 0,
        requester_id: Number(actorUserId) || 2,
      });
      setNotice("Request created (draft).");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  async function runAction(
    requestId: number,
    action: "submit" | "approve" | "refuse",
  ) {
    setBusy(true);
    setError(null);
    try {
      const actor = Number(actorUserId) || 2;
      if (action === "submit") {
        await api.submitProcessRequest(connectionId, requestId);
      } else if (action === "approve") {
        await api.approveProcessRequest(connectionId, requestId, actor);
      } else {
        await api.refuseProcessRequest(connectionId, requestId, actor);
      }
      setNotice(`Request #${requestId}: ${action}`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : `${action} failed`);
    } finally {
      setBusy(false);
    }
  }

  void connection;

  return (
    <div data-testid="approval-processes-panel">
      <p className="ap-lead">
        Standalone request and approve workflows with multi-level chains. Distinct from button
        gating on the Rules tab.
      </p>

      {gate ? (
        <div className="ap-honesty" data-testid="approval-processes-engine">
          <span className="ap-chip">{processEngineLabel(gate.engine)}</span>
          <span className="ap-chip" data-tone={gate.community_models_ready ? "accent" : "quiet"}>
            {gate.community_models_ready ? "Models ready" : "Scaffold required"}
          </span>
        </div>
      ) : null}
      {gate?.enterprise_note ? (
        <p className="ap-inbox-note" data-testid="approval-processes-enterprise-note">
          {gate.enterprise_note}
        </p>
      ) : null}

      <div className="ap-composer-actions" style={{ marginTop: 16 }}>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={busy}
          onClick={() => setConfirmOpen(true)}
          data-testid="approval-processes-scaffold"
        >
          Scaffold Approval Requests
        </Button>
        <Link
          href={`/connections/${connectionId}/wizard`}
          className="text-sm text-muted underline-offset-2 hover:underline"
          data-testid="approval-processes-wizard-link"
        >
          Wizard templates
        </Link>
      </div>

      <section className="ap-composer" data-testid="approval-process-composer">
        <h3 className="ap-composer-title">New request</h3>
        <div className="ap-composer-grid">
          <Select
            label="Type"
            value={typeId}
            onChange={(e) => setTypeId(e.target.value)}
            placeholder="Select a type"
            options={types.map((t) => ({
              value: String(t.id),
              label: `${t.name ?? `Type ${t.id}`} (${t.levels} level(s))`,
            }))}
            data-testid="approval-process-type"
          />
          <Input
            label="Subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            data-testid="approval-process-subject"
          />
          <Input
            label="Amount"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            inputMode="decimal"
            data-testid="approval-process-amount"
          />
          <Input
            label="Actor user id"
            value={actorUserId}
            onChange={(e) => setActorUserId(e.target.value)}
            inputMode="numeric"
            data-testid="approval-process-actor"
          />
        </div>
        <div className="ap-composer-actions">
          <Button
            type="button"
            variant="primary"
            size="sm"
            disabled={busy || !gate?.community_models_ready || !typeId}
            loading={busy}
            onClick={() => void createRequest()}
            data-testid="approval-process-create"
          >
            Create draft request
          </Button>
        </div>
      </section>

      <section className="ap-section" data-testid="approval-process-types">
        <h3 className="ap-list-title">Approval types</h3>
        {!hydrated ? (
          <div className="mt-3 space-y-2">
            <Skeleton className="h-12 w-full" />
          </div>
        ) : types.length === 0 ? (
          <div className="mt-3">
            <ApprovalsStateGuide
              testId="approval-process-types-empty"
              guide={processesEmptyGuide("types")}
              actions={
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setConfirmOpen(true)}
                >
                  Scaffold Approval Requests
                </Button>
              }
            />
          </div>
        ) : (
          <ul className="ap-list">
            {types.map((t) => (
              <li key={t.id}>
                <div className="ap-list-row">
                  <div className="min-w-0">
                    <p className="ap-list-name">{t.name ?? `Type ${t.id}`}</p>
                    <p className="ap-list-meta" style={{ fontFamily: "inherit" }}>
                      {t.levels} level(s)
                      {t.chain[0]?.min_approvals
                        ? ` · L1 min ${t.chain[0].min_approvals}`
                        : ""}
                    </p>
                  </div>
                  <Badge variant={t.active ? "success" : "default"}>
                    {t.active ? "Active" : "Inactive"}
                  </Badge>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="ap-section" data-testid="approval-process-requests">
        <h3 className="ap-list-title">Requests</h3>
        {!hydrated ? (
          <div className="mt-3 space-y-2">
            <Skeleton className="h-12 w-full" />
          </div>
        ) : requests.length === 0 ? (
          <div className="mt-3">
            <ApprovalsStateGuide
              testId="approval-process-requests-empty"
              guide={processesEmptyGuide("requests")}
            />
          </div>
        ) : (
          <ul className="ap-list">
            {requests.map((r) => (
              <li key={r.id} data-testid={`approval-process-request-${r.id}`}>
                <div className="ap-list-row">
                  <div className="min-w-0">
                    <p className="ap-list-name">
                      #{r.id} {r.subject ?? r.name ?? "Request"}
                      {r.current_level ? ` · level ${r.current_level}` : ""}
                    </p>
                    <div className="ap-list-actions">
                      {r.state === "draft" ? (
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          disabled={busy}
                          onClick={() => void runAction(r.id, "submit")}
                        >
                          Send for approval
                        </Button>
                      ) : null}
                      {r.state === "submitted" ? (
                        <>
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            disabled={busy}
                            onClick={() => void runAction(r.id, "approve")}
                          >
                            Approve
                          </Button>
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            disabled={busy}
                            onClick={() => void runAction(r.id, "refuse")}
                          >
                            Refuse
                          </Button>
                        </>
                      ) : null}
                    </div>
                  </div>
                  <Badge variant="info">{r.state ?? "unknown"}</Badge>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {notice ? (
        <Callout variant="info" title="Notice" className="ap-notice">
          {notice}
        </Callout>
      ) : null}
      {error ? (
        <div className="ap-notice">
          <ApprovalsStateGuide
            tone="danger"
            live
            testId="approval-processes-error"
            guide={{
              ...approvalsErrorGuide("scaffold"),
              why: error,
            }}
          />
        </div>
      ) : null}

      <ConfirmDialogV2
        riskLevel="danger"
        open={confirmOpen}
        title="Scaffold Approval Requests"
        warning={error ?? "Creates x_approval_type + x_approval_request on live Odoo."}
        risks={[
          "Live metadata writes",
          "Seeds two-level demo type (min_approvals=2 at level 1)",
          "Try a test copy first",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={(phrase) => void runScaffold(phrase)}
      />
    </div>
  );
}
