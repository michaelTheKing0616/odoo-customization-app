"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { ApprovalProcessesPanel } from "@/components/approvals/ApprovalProcessesPanel";
import {
  api,
  ApprovalButton,
  ApprovalEntry,
  ApprovalRule,
  ApprovalsGateResponse,
  Connection,
} from "@/lib/api";

export default function ApprovalsPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;
  const [tab, setTab] = useState<"buttons" | "processes">("buttons");

  const [connection, setConnection] = useState<Connection | null>(null);
  const [gate, setGate] = useState<ApprovalsGateResponse | null>(null);
  const [rules, setRules] = useState<ApprovalRule[]>([]);
  const [entries, setEntries] = useState<ApprovalEntry[]>([]);
  const [buttons, setButtons] = useState<ApprovalButton[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [model, setModel] = useState("res.partner");
  const [name, setName] = useState("Button approval");
  const [buttonMethod, setButtonMethod] = useState("");
  const [approverUserId, setApproverUserId] = useState("2");
  const [testRecordId, setTestRecordId] = useState("1");

  const refresh = useCallback(async () => {
    const [conn, g, r, e] = await Promise.all([
      api.getConnection(connectionId),
      api.getApprovalsGate(connectionId),
      api.listApprovalRules(connectionId),
      api.listApprovalEntries(connectionId),
    ]);
    setConnection(conn);
    setGate(g);
    setRules(r);
    setEntries(e);
  }, [connectionId]);

  useEffect(() => {
    refresh().catch((err: Error) => setError(err.message));
  }, [refresh]);

  async function loadButtons() {
    setError(null);
    try {
      const rows = await api.listApprovalButtons(connectionId, model.trim());
      setButtons(rows);
      if (rows.length > 0 && !buttonMethod) {
        setButtonMethod(rows[0].name);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Button discovery failed");
    }
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const selected = buttons.find((b) => b.name === buttonMethod);
      await api.createApprovalRule(connectionId, {
        name,
        target_model: model.trim(),
        button_method: buttonMethod,
        button_label: selected?.label ?? buttonMethod,
        engine: gate?.engine === "studio" ? "studio" : "community",
        steps: [
          {
            order: 1,
            approver_user_ids: [Number.parseInt(approverUserId, 10) || 2],
            exclusive: false,
          },
        ],
      });
      setNotice("Approval rule created.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  async function simulateCheck(ruleId: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await api.checkApprovalAction(
        connectionId,
        ruleId,
        Number.parseInt(testRecordId, 10) || 1,
        Number.parseInt(approverUserId, 10) || 2,
      );
      setNotice(res.allowed ? res.message : `Blocked: ${res.message}`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Check failed");
    } finally {
      setBusy(false);
    }
  }

  async function approveEntry(entryId: string, approve: boolean) {
    setBusy(true);
    setError(null);
    try {
      await api.approveApprovalEntry(connectionId, entryId, {
        actor_user_id: Number.parseInt(approverUserId, 10) || 2,
        approve,
      });
      setNotice(approve ? "Entry approved." : "Entry rejected.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Resolve failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="odoo-shell min-h-screen px-6 py-10">
      <div className="mx-auto max-w-5xl">
        <Link href={`/connections/${connectionId}`} className="text-sm text-[#c9a9c0] hover:underline">
          ← Metadata
        </Link>
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl text-[#faf6f9]">
          Approvals
        </h1>
        <p className="mt-1 text-sm text-[#8f7a88]">
          Two distinct patterns: button gating (CMP-5) vs standalone approval processes (CMP-10).
        </p>
        <div className="mt-4 flex gap-4 text-sm">
          <button
            type="button"
            onClick={() => setTab("buttons")}
            className={
              tab === "buttons"
                ? "border-b-2 border-[#c9a9c0] pb-1 text-[#faf6f9]"
                : "text-[#8f7a88]"
            }
          >
            Button approvals
          </button>
          <button
            type="button"
            onClick={() => setTab("processes")}
            className={
              tab === "processes"
                ? "border-b-2 border-[#c9a9c0] pb-1 text-[#faf6f9]"
                : "text-[#8f7a88]"
            }
          >
            Approval processes
          </button>
        </div>
        <VersionAwarenessBanner capabilities={connection?.capabilities} />

        {tab === "processes" ? (
          <ApprovalProcessesPanel connectionId={connectionId} connection={connection} />
        ) : (
          <>
        <p className="mt-3 text-sm text-[#8f7a88]">
          Studio-style button gating — Community engine by default; Studio native when detected.
        </p>

        {gate && (
          <p className="mt-3 text-sm text-[#c9a9c0]">
            Engine:{" "}
            <span className="font-medium text-[#faf6f9]">
              {gate.engine === "studio" ? "Enterprise Studio" : "Community"}
            </span>
            {gate.studio_note ? (
              <span className="mt-1 block text-xs text-[#e8d09f]">{gate.studio_note}</span>
            ) : null}
          </p>
        )}

        {error && <p className="mt-4 text-sm text-[#f0a8a0]">{error}</p>}
        {notice && <p className="mt-4 text-sm text-[#c9a9c0]">{notice}</p>}

        <section className="mt-8 border border-[#3d2a38] bg-[#0f1a16]/70 p-4">
          <h2 className="font-[family-name:var(--font-display)] text-xl text-[#faf6f9]">
            New rule
          </h2>
          <form onSubmit={(e) => void onCreate(e)} className="mt-4 space-y-3 text-sm">
            <label className="block">
              <span className="text-[#8f7a88]">Model</span>
              <input
                className="mt-1 w-full border border-[#3d2a38] bg-[#120e14] px-2 py-1.5 text-[#faf6f9]"
                value={model}
                onChange={(e) => setModel(e.target.value)}
              />
            </label>
            <button
              type="button"
              onClick={() => void loadButtons()}
              className="border border-[#5a3d4a] px-3 py-1 text-xs text-[#c9a9c0]"
            >
              Discover buttons
            </button>
            <label className="block">
              <span className="text-[#8f7a88]">Button method</span>
              <select
                className="mt-1 w-full border border-[#3d2a38] bg-[#120e14] px-2 py-1.5 text-[#faf6f9]"
                value={buttonMethod}
                onChange={(e) => setButtonMethod(e.target.value)}
              >
                <option value="">Select…</option>
                {buttons.map((b) => (
                  <option key={b.name} value={b.name}>
                    {b.label || b.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-[#8f7a88]">Rule name</span>
              <input
                className="mt-1 w-full border border-[#3d2a38] bg-[#120e14] px-2 py-1.5 text-[#faf6f9]"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label className="block">
              <span className="text-[#8f7a88]">Approver user id</span>
              <input
                className="mt-1 w-full border border-[#3d2a38] bg-[#120e14] px-2 py-1.5 text-[#faf6f9]"
                value={approverUserId}
                onChange={(e) => setApproverUserId(e.target.value)}
              />
            </label>
            <button
              type="submit"
              disabled={busy || !buttonMethod}
              className="border border-[#c9a9c0] px-3 py-1.5 text-xs text-[#c9a9c0] disabled:opacity-40"
            >
              Create rule
            </button>
          </form>
        </section>

        <section className="mt-8">
          <h2 className="font-[family-name:var(--font-display)] text-xl text-[#faf6f9]">Rules</h2>
          <ul className="mt-4 space-y-3">
            {rules.map((r) => (
              <li key={r.id} className="border border-[#3d2a38] bg-[#0f1a16]/70 p-4 text-sm">
                <p className="font-medium text-[#faf6f9]">
                  {r.name}{" "}
                  <span className="text-xs text-[#8f7a88]">
                    ({r.engine}) · {r.target_model}.{r.button_method}
                  </span>
                </p>
                <div className="mt-2 flex flex-wrap gap--2">
                  <input
                    className="w-24 border border-[#3d2a38] bg-[#120e14] px-2 py-1 text-xs text-[#faf6f9]"
                    value={testRecordId}
                    onChange={(e) => setTestRecordId(e.target.value)}
                    aria-label="Test record id"
                  />
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void simulateCheck(r.id)}
                    className="border border-[#5a3d4a] px-2 py-1 text-xs text-[#c9a9c0]"
                  >
                    Simulate click
                  </button>
                </div>
              </li>
            ))}
            {rules.length === 0 && (
              <li className="text-sm text-[#8f7a88]">No approval rules yet.</li>
            )}
          </ul>
        </section>

        <section className="mt-10">
          <h2 className="font-[family-name:var(--font-display)] text-xl text-[#faf6f9]">
            Entries / audit
          </h2>
          <ul className="mt-4 space-y-2 text-sm">
            {entries.map((e) => (
              <li key={e.id} className="border border-[#3d2a38] bg-[#0f1a16]/70 p-3">
                <p className="text-[#faf6f9]">
                  {e.record_model} #{e.record_id} · step {e.step_order} · {e.status}
                </p>
                <p className="text-xs text-[#8f7a88]">{e.message}</p>
                {e.status === "pending" && (
                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void approveEntry(e.id, true)}
                      className="border border-[#c9a9c0] px-2 py-1 text-xs text-[#c9a9c0]"
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void approveEntry(e.id, false)}
                      className="border border-[#5a3d4a] px-2 py-1 text-xs text-[#8f7a88]"
                    >
                      Reject
                    </button>
                  </div>
                )}
              </li>
            ))}
            {entries.length === 0 && (
              <li className="text-[#8f7a88]">No approval entries yet.</li>
            )}
          </ul>
        </section>
          </>
        )}
      </div>
    </main>
  );
}
