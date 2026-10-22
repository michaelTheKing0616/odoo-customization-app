"use client";

import { useParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
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
import { ReminderSchedulePreview } from "@/components/reminders/ReminderSchedulePreview";
import { ReminderStateGuide } from "@/components/reminders/ReminderStateGuide";
import { ReminderStepRail } from "@/components/reminders/ReminderStepRail";
import { ReminderStudioBar } from "@/components/reminders/ReminderStudioBar";
import {
  CONFIRM_PHRASE,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  PRIMARY_CTA,
  canSubmitReminder,
  emptyReminderGuide,
  reminderCreatedGuide,
  reminderErrorGuide,
  reminderHonestyGuide,
  resolveReminderStep,
  type ReminderErrorContext,
  type ReminderIntervalType,
  type ReminderMode,
} from "@/lib/remindersScreen";
import "@/components/reminders/reminders-operate.css";
import { FrameMeta } from "@/components/frame/FrameMeta";

export default function RemindersPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [name, setName] = useState("Loan overdue reminder");
  const [model, setModel] = useState("x_lib_loan");
  const [dateField, setDateField] = useState("x_due_date");
  const [mode, setMode] = useState<ReminderMode>("overdue");
  const [dueSoonDays, setDueSoonDays] = useState(2);
  const [intervalNumber, setIntervalNumber] = useState(1);
  const [intervalType, setIntervalType] = useState<ReminderIntervalType>("days");
  const [emailTo, setEmailTo] = useState("{{ object.x_member_id.email }}");
  const [createCron, setCreateCron] = useState(true);
  const [scheduleTouched, setScheduleTouched] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorContext, setErrorContext] = useState<ReminderErrorContext>("load");
  const [result, setResult] = useState<ReminderCreateOut | null>(null);

  useEffect(() => {
    api
      .getConnection(connectionId)
      .then(setConnection)
      .catch((err: Error) => {
        setErrorContext("load");
        setError(err.message);
      });
  }, [connectionId]);

  const canCreate = advancedMutationAllowed(connection);
  const createBlocked = advancedMutationBlockedReason(connection);

  const currentStep = resolveReminderStep({
    hasResult: Boolean(result),
    confirmOpen,
    scheduleTouched,
    composing: true,
  });

  const submitReady = canSubmitReminder({
    name,
    model,
    dateField,
    canCreate,
  });

  const honesty = useMemo(() => reminderHonestyGuide(createCron), [createCron]);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    if (!name.trim() || !model.trim() || !dateField.trim()) {
      setErrorContext("validate");
      setError("Name, model, and date field are required.");
      return;
    }
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
        setErrorContext("confirm");
        setError(err.warning);
      } else {
        setErrorContext("create");
        setError(err instanceof Error ? err.message : "Create reminder failed");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="reminders-operate p-4 sm:p-6" data-testid="reminders-page">
      <header className="rm-studio" data-testid="reminders-studio-chrome">
        <div className="rm-titlebar">
          <div className="rm-title-block">
            <FrameMeta />
            <p className="rm-kicker">{connection?.name ?? connectionId}</p>
            <h1 className="rm-title">{PAGE_TITLE}</h1>
            <p className="rm-subtitle">{PAGE_DESCRIPTION}</p>
          </div>
        </div>
        <ReminderStudioBar
          step={currentStep}
          honesty={!result ? honesty : null}
        />
        <ReminderStepRail current={currentStep} />
      </header>

      <div className="rm-desk">
        <div className="rm-paper">
          <VersionAwarenessBanner capabilities={connection?.capabilities} />

          {createBlocked ? (
            <Callout variant="warning" title="Changes are switched off">
              {createBlocked}
            </Callout>
          ) : null}

          {error ? (
            <ReminderStateGuide
              testId="reminders-error-guide"
              tone="danger"
              live
              guide={reminderErrorGuide(errorContext, error)}
            />
          ) : null}

          {busy ? (
            <div className="rm-progress" aria-busy="true" data-testid="reminders-busy" role="status">
              Creating reminder on Odoo…
            </div>
          ) : null}

          {!result ? (
            <ReminderStateGuide
              density="brief"
              testId="reminders-empty-guide"
              guide={emptyReminderGuide()}
            />
          ) : null}

          <section className="rm-panel" aria-labelledby="reminders-compose-title">
            <h2 id="reminders-compose-title" className="rm-panel-title">
              Compose reminder
            </h2>
            <p className="rm-panel-sub">
              {PRIMARY_CTA} is the only teal primary. Schedule honesty lives in the studio bar.
            </p>

            <form onSubmit={onSubmit} className="rm-field-grid">
              <label className="rm-field">
                Name
                <input
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  data-testid="reminders-name-input"
                />
              </label>
              <div className="rm-field-grid rm-cols-2">
                <label className="rm-field">
                  Model
                  <input
                    required
                    className="font-mono"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder="x_lib_loan"
                    data-testid="reminders-model-input"
                  />
                </label>
                <label className="rm-field">
                  Date field
                  <input
                    required
                    className="font-mono"
                    value={dateField}
                    onChange={(e) => setDateField(e.target.value)}
                    placeholder="x_due_date"
                    data-testid="reminders-date-field-input"
                  />
                </label>
              </div>
              <div className="rm-field-grid rm-cols-2">
                <label className="rm-field">
                  Mode
                  <select
                    value={mode}
                    onChange={(e) => setMode(e.target.value as ReminderMode)}
                    data-testid="reminders-mode-select"
                  >
                    <option value="overdue">Overdue</option>
                    <option value="due_soon">Due soon</option>
                  </select>
                </label>
                {mode === "due_soon" ? (
                  <label className="rm-field">
                    Due soon days
                    <input
                      type="number"
                      min={1}
                      max={30}
                      value={String(dueSoonDays)}
                      onChange={(e) => setDueSoonDays(Number(e.target.value) || 2)}
                      data-testid="reminders-due-soon-days"
                    />
                  </label>
                ) : (
                  <div />
                )}
              </div>

              <div
                className="rm-field-grid"
                onFocusCapture={() => setScheduleTouched(true)}
                data-testid="reminders-schedule-section"
              >
                <h3 className="rm-panel-title">Schedule</h3>
                <p className="rm-panel-sub">
                  Create cron writes an active ir.cron. Leave it off for template-only.
                </p>
                <div className="rm-field-grid rm-cols-2">
                  <label className="rm-field">
                    Interval number
                    <input
                      type="number"
                      min={1}
                      max={365}
                      value={String(intervalNumber)}
                      onChange={(e) => {
                        setScheduleTouched(true);
                        setIntervalNumber(Number(e.target.value) || 1);
                      }}
                      data-testid="reminders-interval-number"
                    />
                  </label>
                  <label className="rm-field">
                    Interval type
                    <select
                      value={intervalType}
                      onChange={(e) => {
                        setScheduleTouched(true);
                        setIntervalType(e.target.value as ReminderIntervalType);
                      }}
                      data-testid="reminders-interval-type"
                    >
                      <option value="minutes">Minutes</option>
                      <option value="hours">Hours</option>
                      <option value="days">Days</option>
                      <option value="weeks">Weeks</option>
                      <option value="months">Months</option>
                    </select>
                  </label>
                </div>
                <label className="rm-field">
                  Email to
                  <input
                    className="font-mono"
                    value={emailTo}
                    onChange={(e) => setEmailTo(e.target.value)}
                    data-testid="reminders-email-to"
                  />
                </label>
                <label className="rm-check">
                  <input
                    type="checkbox"
                    checked={createCron}
                    onChange={(e) => {
                      setScheduleTouched(true);
                      setCreateCron(e.target.checked);
                    }}
                    data-testid="reminders-create-cron"
                  />
                  <span>
                    Create cron (schedule enabled)
                    <span className="rm-check-hint">
                      When on, Odoo gets an active ir.cron that searches by the date
                      field and queues the template. When off, only the template is
                      created.
                    </span>
                  </span>
                </label>
                <ReminderSchedulePreview
                  createCron={createCron}
                  mode={mode}
                  intervalNumber={intervalNumber}
                  intervalType={intervalType}
                  dueSoonDays={dueSoonDays}
                  dateField={dateField}
                />
              </div>

              <div className="rm-actions">
                <Button
                  type="submit"
                  variant="primary"
                  disabled={busy || !submitReady}
                  title={createBlocked ?? undefined}
                  loading={busy}
                  data-testid="reminders-create-btn"
                >
                  {PRIMARY_CTA}
                </Button>
                <p className="text-xs text-muted">
                  Live write. Confirm phrase required. Studio bar keeps schedule honesty accurate.
                </p>
              </div>
            </form>
          </section>

          {result ? (
            <div
              className="rm-result"
              data-testid="reminders-result"
              data-scheduled={result.cron_id != null ? "true" : "false"}
            >
              <ReminderStateGuide
                testId="reminders-created-guide"
                tone={result.cron_id != null ? "success" : "warning"}
                guide={reminderCreatedGuide({
                  mailTemplateId: result.mail_template_id,
                  cronId: result.cron_id,
                })}
              />
              <p className="text-sm text-muted">{result.message}</p>
              <div className="rm-ids">
                <span>
                  Template{" "}
                  <code data-testid="reminders-template-id">
                    {result.mail_template_id ?? "none"}
                  </code>
                </span>
                <span>
                  Cron{" "}
                  <code data-testid="reminders-cron-id">
                    {result.cron_id != null ? result.cron_id : "none (schedule off)"}
                  </code>
                </span>
              </div>
              {result.warnings && result.warnings.length > 0 ? (
                <Callout variant="warning" title="Warnings">
                  <ul className="list-disc space-y-1 pl-5">
                    {result.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                </Callout>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>

      <ConfirmDialogV2
        open={confirmOpen}
        riskLevel="danger"
        title="Create reminder on Odoo"
        warning={
          createCron
            ? "Creates a mail.template and an active ir.cron on the live Odoo database. Emails may be queued depending on outgoing mail config."
            : "Creates a mail.template only (no ir.cron). Nothing sends automatically until you schedule it elsewhere."
        }
        risks={
          createCron
            ? [
                "Live mail.template write",
                "Active schedule will email matching records on the interval",
                "Requires mail module and valid email_to expression",
              ]
            : [
                "Live mail.template write",
                "No cron created; schedule stays off",
                "Requires mail module and valid email_to expression",
              ]
        }
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={onConfirm}
      />
    </div>
  );
}
