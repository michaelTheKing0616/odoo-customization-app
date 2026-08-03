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
import { ConfirmDialog } from "@/components/ConfirmDialog";

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
    refresh().catch((err: Error) => setError(err.message));
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

  return (
    <div>
      <p className="mt-2 text-sm text-[#8f7a88]">
        Standalone request/approve workflows (multi-level chains, min-approvals). Distinct from
        button gating above — compendium §17.
      </p>

      {gate && (
        <p className="mt-3 text-sm text-[#c9a9c0]">
          Process engine:{" "}
          <span className="font-medium text-[#faf6f9]">
            {gate.engine === "enterprise" ? "Enterprise approvals" : "Community x_approval_*"}
          </span>
          {gate.community_models_ready ? " · models ready" : " · scaffold required"}
          {gate.enterprise_note ? (
            <span className="mt-1 block text-xs text-[#e8d09f]">{gate.enterprise_note}</span>
          ) : null}
        </p>
      )}

      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          disabled={busy}
          onClick={() => setConfirmOpen(true)}
          className="border border-[#c9a9c0] px-3 py-1.5 text-sm text-[#c9a9c0] disabled:opacity-50"
        >
          Scaffold Approval Requests
        </button>
        <Link
          href={`/connections/${connectionId}/wizard`}
          className="border border-[#5a3d4a] px-3 py-1.5 text-sm text-[#8f7a88]"
        >
          Wizard templates
        </Link>
      </div>

      <section className="mt-8 border border-[#3d2a38] bg-[#0f1a16]/70 p-4">
        <h3 className="font-[family-name:var(--font-display)] text-lg text-[#faf6f9]">
          New request
        </h3>
        <div className="mt-3 grid gap-3 md:grid-cols-2 text-sm">
          <label className="block">
            <span className="text-[#8f7a88]">Type</span>
            <select
              className="mt-1 w-full border border-[#3d2a38] bg-[#120e14] px-2 py-1.5 text-[#faf6f9]"
              value={typeId}
              onChange={(e) => setTypeId(e.target.value)}
            >
              <option value="">Select…</option>
              {types.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} ({t.levels} level(s))
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-[#8f7a88]">Subject</span>
            <input
              className="mt-1 w-full border border-[#3d2a38] bg-[#120e14] px-2 py-1.5 text-[#faf6f9]"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-[#8f7a88]">Amount</span>
            <input
              className="mt-1 w-full border border-[#3d2a38] bg-[#120e14] px-2 py-1.5 text-[#faf6f9]"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-[#8f7a88]">Actor user id</span>
            <input
              className="mt-1 w-full border border-[#3d2a38] bg-[#120e14] px-2 py-1.5 text-[#faf6f9]"
              value={actorUserId}
              onChange={(e) => setActorUserId(e.target.value)}
            />
          </label>
        </div>
        <button
          type="button"
          disabled={busy || !gate?.community_models_ready}
          onClick={() => void createRequest()}
          className="mt-3 border border-[#c9a9c0] px-3 py-1.5 text-xs text-[#c9a9c0] disabled:opacity-40"
        >
          Create draft request
        </button>
      </section>

      <section className="mt-8">
        <h3 className="font-[family-name:var(--font-display)] text-lg text-[#faf6f9]">
          Approval types
        </h3>
        <ul className="mt-3 space-y-2 text-sm">
          {types.map((t) => (
            <li key={t.id} className="border border-[#3d2a38] bg-[#0f1a16]/70 p-3">
              <span className="text-[#faf6f9]">{t.name}</span>
              <span className="text-xs text-[#8f7a88]">
                {" "}
                · {t.levels} level(s)
                {t.chain[0]?.min_approvals
                  ? ` · L1 min ${t.chain[0].min_approvals}`
                  : ""}
              </span>
            </li>
          ))}
          {types.length === 0 && (
            <li className="text-[#8f7a88]">No types — scaffold the template first.</li>
          )}
        </ul>
      </section>

      <section className="mt-8">
        <h3 className="font-[family-name:var(--font-display)] text-lg text-[#faf6f9]">
          Requests
        </h3>
        <ul className="mt-3 space-y-2 text-sm">
          {requests.map((r) => (
            <li key={r.id} className="border border-[#3d2a38] bg-[#0f1a16]/70 p-3">
              <p className="text-[#faf6f9]">
                #{r.id} {r.subject ?? r.name} · {r.state}
                {r.current_level ? ` · level ${r.current_level}` : ""}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {r.state === "draft" && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void runAction(r.id, "submit")}
                    className="border border-[#c9a9c0] px-2 py-1 text-xs"
                  >
                    Send for approval
                  </button>
                )}
                {r.state === "submitted" && (
                  <>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void runAction(r.id, "approve")}
                      className="border border-[#c9a9c0] px-2 py-1 text-xs"
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void runAction(r.id, "refuse")}
                      className="border border-[#5a3d4a] px-2 py-1 text-xs text-[#8f7a88]"
                    >
                      Refuse
                    </button>
                  </>
                )}
              </div>
            </li>
          ))}
          {requests.length === 0 && (
            <li className="text-[#8f7a88]">No approval requests yet.</li>
          )}
        </ul>
      </section>

      {notice && <p className="mt-4 text-sm text-[#c9a9c0]">{notice}</p>}
      {error && <p className="mt-4 text-sm text-[#f0a8a0]">{error}</p>}

      <ConfirmDialog
        open={confirmOpen}
        title="Scaffold Approval Requests"
        warning={error ?? "Creates x_approval_type + x_approval_request on live Odoo."}
        risks={[
          "Live metadata writes",
          "Seeds two-level demo type (min_approvals=2 at level 1)",
          "Prefer sandbox first",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={(phrase) => void runScaffold(phrase)}
      />
    </div>
  );
}
