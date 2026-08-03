"use client";

import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
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
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Card, PageHeader } from "@/components/ui/layout-primitives";

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

  const canCreate = advancedMutationAllowed(connection);
  const createBlocked = advancedMutationBlockedReason(connection);

  return (
    <div className="mx-auto max-w-2xl" data-testid="reminders-page">
      <PageHeader
        title="Reminder wizard"
        description={`${connection?.name ?? connectionId} · mail.template + optional ir.cron`}
      />
      <VersionAwarenessBanner capabilities={connection?.capabilities} />
      {createBlocked ? (
        <Callout variant="warning" title="Mutations blocked" className="mt-4">
          {createBlocked}
        </Callout>
      ) : null}

      {error ? <ErrorNotice message={error} className="mt-4" /> : null}

      <Card className="mt-8 p-6">
        <form onSubmit={onSubmit} className="space-y-4">
          <Input label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
          <Input
            label="Model"
            required
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="x_lib_loan"
            className="font-mono text-sm"
          />
          <Input
            label="Date field"
            required
            value={dateField}
            onChange={(e) => setDateField(e.target.value)}
            placeholder="x_due_date"
            className="font-mono text-sm"
          />
          <Select
            label="Mode"
            options={[
              { value: "overdue", label: "overdue" },
              { value: "due_soon", label: "due_soon" },
            ]}
            value={mode}
            onChange={(e) => setMode(e.target.value as "overdue" | "due_soon")}
          />
          {mode === "due_soon" ? (
            <Input
              label="Due soon days"
              type="number"
              min={1}
              max={30}
              value={String(dueSoonDays)}
              onChange={(e) => setDueSoonDays(Number(e.target.value) || 2)}
            />
          ) : null}
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Interval number"
              type="number"
              min={1}
              max={365}
              value={String(intervalNumber)}
              onChange={(e) => setIntervalNumber(Number(e.target.value) || 1)}
            />
            <Select
              label="Interval type"
              options={[
                { value: "minutes", label: "minutes" },
                { value: "hours", label: "hours" },
                { value: "days", label: "days" },
                { value: "weeks", label: "weeks" },
                { value: "months", label: "months" },
              ]}
              value={intervalType}
              onChange={(e) => setIntervalType(e.target.value)}
            />
          </div>
          <Input
            label="Email to"
            value={emailTo}
            onChange={(e) => setEmailTo(e.target.value)}
            className="font-mono text-sm"
          />
          <label className="flex items-start gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={createCron}
              onChange={(e) => setCreateCron(e.target.checked)}
              className="mt-1"
            />
            <span>
              Create cron
              <span className="mt-0.5 block text-xs text-muted">
                Schedules an ir.cron that searches by date field and sends the template.
              </span>
            </span>
          </label>
          <Button
            type="submit"
            variant="primary"
            disabled={busy || !canCreate}
            title={createBlocked ?? undefined}
            loading={busy}
          >
            Create reminder
          </Button>
        </form>
      </Card>

      {result ? (
        <Card className="mt-6 p-5">
          <h2 className="text-xl font-semibold text-ink">Created</h2>
          <p className="mt-2 text-sm text-muted">{result.message}</p>
          <p className="mt-1 text-sm text-muted">
            Template <code className="text-ink">{result.mail_template_id ?? "—"}</code>
            {result.cron_id != null ? (
              <>
                {" "}
                · Cron <code className="text-ink">{result.cron_id}</code>
              </>
            ) : null}
          </p>
          {result.warnings && result.warnings.length > 0 ? (
            <Callout variant="warning" title="Warnings" className="mt-3">
              <ul className="list-disc space-y-1 pl-5">
                {result.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </Callout>
          ) : null}
        </Card>
      ) : null}

      <ConfirmDialogV2
        open={confirmOpen}
        riskLevel="danger"
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
    </div>
  );
}
