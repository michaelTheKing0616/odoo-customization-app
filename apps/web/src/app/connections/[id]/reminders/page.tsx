"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import {
  api,
  ConfirmationRequiredError,
  Connection,
  ReminderCreateOut,
} from "@/lib/api";
import {
  advancedMutationAllowed,
  advancedMutationBlockedReason,
} from "@/lib/capabilities";

const CONFIRM_PHRASE = "I understand the risks";

export default function RemindersPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [name, setName] = useState("Loan overdue reminder");
  const [model, setModel] = useState("x_lib_loan");
  const [dateField, setDateField] = useState("x_due_date");
  const [mode, setMode] = useState<"overdue" | "due_soon">("overdue");
  const [dueSoonDays, setDueSoonDays] = useState(2);
  const [intervalNumber, setIntervalNumber] = useState(1);
  const [intervalType, setIntervalType] = useState("days");
  const [emailTo, setEmailTo] = useState("{{ object.x_member_id.email }}");
  const [createCron, setCreateCron] = useState(true);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReminderCreateOut | null>(null);

  useEffect(() => {
    api
      .getConnection(connectionId)
      .then(setConnection)
      .catch((err: Error) => setError(err.message));
  }, [connectionId]);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setConfirmOpen(true);
  }

  async function onConfirm(phrase: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await api.createReminder(connectionId, {
        name: name.trim(),
        model: model.trim(),
        date_field: dateField.trim(),
        mode,
        due_soon_days: dueSoonDays,
        interval_number: intervalNumber,
        interval_type: intervalType,
        email_to: emailTo.trim(),
        create_cron: createCron,
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setResult(res);
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Create reminder failed");
      }
    } finally {
      setBusy(false);
    }
  }

  // Reminder create is confirm-gated (mail.template + optional cron) → advanced.
  const canCreate = advancedMutationAllowed(connection);
  const createBlocked = advancedMutationBlockedReason(connection);

  return (
    <main className="min-h-screen bg-[radial-gradient(ellipse_at_top,_#3d2a38_0%,_#1a1218_50%,_#0c090b_100%)] px-6 py-10 text-[#f4eef2]">
      <div className="mx-auto max-w-2xl">
        <div className="flex flex-wrap gap-4 text-sm">
          <Link
            href={`/connections/${connectionId}`}
            className="text-[#c9a9c0] hover:underline"
          >
            ← Metadata
          </Link>
          <Link
            href={`/connections/${connectionId}/wizard`}
            className="text-[#8f7a88] hover:underline"
          >
            Wizard
          </Link>
          <Link
            href={`/connections/${connectionId}/automations`}
            className="text-[#8f7a88] hover:underline"
          >
            Automations
          </Link>
        </div>

        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl text-[#faf6f9]">
          Reminder wizard
        </h1>
        <p className="mt-1 text-sm text-[#8f7a88]">
          {connection
            ? `${connection.name} · mail.template + optional ir.cron`
            : connectionId}
        </p>
        <VersionAwarenessBanner capabilities={connection?.capabilities} />
        {createBlocked && (
          <p className="mt-2 text-sm text-[#e8d09f]">{createBlocked}</p>
        )}

        {error && <p className="mt-4 text-sm text-[#f0a8a0]">{error}</p>}

        <form
          onSubmit={onSubmit}
          className="mt-8 space-y-4 border border-[#3d2a38] bg-[#0f1a16]/70 p-6"
        >
          <label className="block text-sm">
            <span className="text-[#a8909e]">Name</span>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
            />
          </label>
          <label className="block text-sm">
            <span className="text-[#a8909e]">Model</span>
            <input
              required
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="x_lib_loan"
              className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
            />
          </label>
          <label className="block text-sm">
            <span className="text-[#a8909e]">Date field</span>
            <input
              required
              value={dateField}
              onChange={(e) => setDateField(e.target.value)}
              placeholder="x_due_date"
              className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
            />
          </label>
          <label className="block text-sm">
            <span className="text-[#a8909e]">Mode</span>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as "overdue" | "due_soon")}
              className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
            >
              <option value="overdue">overdue</option>
              <option value="due_soon">due_soon</option>
            </select>
          </label>
          {mode === "due_soon" && (
            <label className="block text-sm">
              <span className="text-[#a8909e]">Due soon days</span>
              <input
                type="number"
                min={1}
                max={30}
                value={dueSoonDays}
                onChange={(e) => setDueSoonDays(Number(e.target.value) || 2)}
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
              />
            </label>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="text-[#a8909e]">Interval number</span>
              <input
                type="number"
                min={1}
                max={365}
                value={intervalNumber}
                onChange={(e) => setIntervalNumber(Number(e.target.value) || 1)}
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
              />
            </label>
            <label className="block text-sm">
              <span className="text-[#a8909e]">Interval type</span>
              <select
                value={intervalType}
                onChange={(e) => setIntervalType(e.target.value)}
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
              >
                <option value="minutes">minutes</option>
                <option value="hours">hours</option>
                <option value="days">days</option>
                <option value="weeks">weeks</option>
                <option value="months">months</option>
              </select>
            </label>
          </div>
          <label className="block text-sm">
            <span className="text-[#a8909e]">Email to</span>
            <input
              value={emailTo}
              onChange={(e) => setEmailTo(e.target.value)}
              className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
            />
          </label>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={createCron}
              onChange={(e) => setCreateCron(e.target.checked)}
              className="mt-1"
            />
            <span>
              <span className="text-[#a8909e]">Create cron</span>
              <span className="mt-0.5 block text-xs text-[#8f7a88]">
                Schedules an ir.cron that searches by date field and sends the
                template.
              </span>
            </span>
          </label>
          <button
            type="submit"
            disabled={busy || !canCreate}
            title={createBlocked ?? undefined}
            className="h-11 bg-[#714B67] px-5 text-sm font-semibold text-white disabled:opacity-60"
          >
            Create reminder
          </button>
        </form>

        {result && (
          <section className="mt-6 border border-[#3d2a38] bg-[#0f1a16]/70 p-5">
            <h2 className="font-[family-name:var(--font-display)] text-xl text-[#faf6f9]">
              Created
            </h2>
            <p className="mt-2 text-sm text-[#c9a9c0]">{result.message}</p>
            <p className="mt-1 text-sm text-[#8f7a88]">
              Template{" "}
              <code className="text-[#c9a9c0]">
                {result.mail_template_id ?? "—"}
              </code>
              {result.cron_id != null && (
                <>
                  {" "}
                  · Cron{" "}
                  <code className="text-[#c9a9c0]">{result.cron_id}</code>
                </>
              )}
            </p>
            {result.warnings && result.warnings.length > 0 && (
              <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-[#f0c090]">
                {result.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            )}
          </section>
        )}
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title="Create reminder on Odoo"
        warning="Creates a mail.template and optionally an ir.cron on the live Odoo database. Emails may be queued depending on outgoing mail config."
        risks={[
          "Live mail.template write",
          "Scheduled code cron may email many records",
          "Requires mail module and valid email_to expression",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={onConfirm}
      />
    </main>
  );
}
