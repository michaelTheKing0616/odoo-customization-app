"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { ReminderSchedulePreview } from "@/components/reminders/ReminderSchedulePreview";
import { ReminderStateGuide } from "@/components/reminders/ReminderStateGuide";
import { ReminderStepRail } from "@/components/reminders/ReminderStepRail";
import { ReminderStudioBar } from "@/components/reminders/ReminderStudioBar";
import {
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  PRIMARY_CTA,
  emptyReminderGuide,
  reminderCreatedGuide,
  reminderErrorGuide,
  reminderHonestyGuide,
  type ReminderStepId,
} from "@/lib/remindersScreen";
import "@/components/reminders/reminders-operate.css";

const STATES = [
  "empty",
  "schedule",
  "template-only",
  "confirm",
  "created",
  "created-template",
  "error",
] as const;
type HarnessState = (typeof STATES)[number];

function stepFor(state: HarnessState): ReminderStepId {
  if (state === "created" || state === "created-template") return "created";
  if (state === "confirm") return "confirm";
  if (state === "schedule" || state === "template-only") return "schedule";
  return "compose";
}

function createCronFor(state: HarnessState): boolean {
  return state !== "template-only" && state !== "created-template";
}

function RemindersHarnessInner() {
  const searchParams = useSearchParams();
  const raw = searchParams.get("state") || "empty";
  const state = (STATES.includes(raw as HarnessState) ? raw : "empty") as HarnessState;
  const createCron = createCronFor(state);
  const step = stepFor(state);
  const showHonesty = state !== "created" && state !== "created-template";
  const showEmptyBrief =
    state === "empty" ||
    state === "schedule" ||
    state === "template-only" ||
    state === "confirm";

  return (
    <div
      className="reminders-operate p-4 sm:p-6"
      data-testid="reminders-page"
      data-harness-state={state}
    >
      <header className="rm-studio" data-testid="reminders-studio-chrome">
        <div className="rm-titlebar">
          <div className="rm-title-block">
            <p className="rm-kicker">E2E mock connection</p>
            <h1 className="rm-title">{PAGE_TITLE}</h1>
            <p className="rm-subtitle">{PAGE_DESCRIPTION}</p>
          </div>
        </div>
        <ReminderStudioBar
          step={step}
          honesty={showHonesty ? reminderHonestyGuide(createCron) : null}
        />
        <ReminderStepRail current={step} />
      </header>

      <div className="rm-desk">
        <div className="rm-paper">
          {state === "error" ? (
            <ReminderStateGuide
              testId="reminders-error-guide"
              tone="danger"
              live
              guide={reminderErrorGuide("create", "Model x_lib_loan not found")}
            />
          ) : null}

          {state === "confirm" ? (
            <ReminderStateGuide
              testId="reminders-confirm-hint"
              tone="warning"
              guide={{
                title: "Confirm phrase required",
                why: "Live mail.template write. With Create cron on, an active schedule will email matching records.",
                next: "Type I understand the risks, then confirm Create the reminder.",
              }}
            />
          ) : null}

          {showEmptyBrief ? (
            <ReminderStateGuide
              density="brief"
              testId="reminders-empty-guide"
              guide={emptyReminderGuide()}
            />
          ) : null}

          <section className="rm-panel" aria-labelledby="harness-compose-title">
            <h2 id="harness-compose-title" className="rm-panel-title">
              Compose reminder
            </h2>
            <p className="rm-panel-sub">
              Harness twin of /connections/[id]/reminders for vision and axe.
            </p>

            <div className="rm-field-grid">
              <label className="rm-field">
                Name
                <input
                  readOnly
                  value="Loan overdue reminder"
                  data-testid="reminders-name-input"
                />
              </label>
              <div className="rm-field-grid rm-cols-2">
                <label className="rm-field">
                  Model
                  <input
                    readOnly
                    className="font-mono"
                    value="x_lib_loan"
                    data-testid="reminders-model-input"
                  />
                </label>
                <label className="rm-field">
                  Date field
                  <input
                    readOnly
                    className="font-mono"
                    value="x_due_date"
                    data-testid="reminders-date-field-input"
                  />
                </label>
              </div>
              <label className="rm-field">
                Mode
                <select disabled value="overdue" data-testid="reminders-mode-select">
                  <option value="overdue">Overdue</option>
                </select>
              </label>

              <div data-testid="reminders-schedule-section">
                <h3 className="rm-panel-title">Schedule</h3>
                <p className="rm-panel-sub">
                  Create cron writes an active ir.cron. Leave it off for template-only.
                </p>
                <div className="rm-field-grid rm-cols-2">
                  <label className="rm-field">
                    Interval number
                    <input
                      readOnly
                      value="1"
                      data-testid="reminders-interval-number"
                    />
                  </label>
                  <label className="rm-field">
                    Interval type
                    <select disabled value="days" data-testid="reminders-interval-type">
                      <option value="days">Days</option>
                    </select>
                  </label>
                </div>
                <label className="rm-field">
                  Email to
                  <input
                    readOnly
                    className="font-mono"
                    value="{{ object.x_member_id.email }}"
                    data-testid="reminders-email-to"
                  />
                </label>
                <label className="rm-check">
                  <input
                    type="checkbox"
                    checked={createCron}
                    readOnly
                    data-testid="reminders-create-cron"
                  />
                  <span>
                    Create cron (schedule enabled)
                    <span className="rm-check-hint">
                      When on, Odoo gets an active ir.cron. When off, template only.
                    </span>
                  </span>
                </label>
                <ReminderSchedulePreview
                  createCron={createCron}
                  mode="overdue"
                  intervalNumber={1}
                  intervalType="days"
                  dueSoonDays={2}
                  dateField="x_due_date"
                />
              </div>

              <div className="rm-actions">
                <Button
                  type="button"
                  variant="primary"
                  disabled={state === "error"}
                  data-testid="reminders-create-btn"
                >
                  {PRIMARY_CTA}
                </Button>
              </div>
            </div>
          </section>

          {state === "created" || state === "created-template" ? (
            <div
              className="rm-result"
              data-testid="reminders-result"
              data-scheduled={state === "created" ? "true" : "false"}
            >
              <ReminderStateGuide
                testId="reminders-created-guide"
                tone={state === "created" ? "success" : "warning"}
                guide={reminderCreatedGuide({
                  mailTemplateId: 44,
                  cronId: state === "created" ? 91 : null,
                })}
              />
              <p className="text-sm text-muted">
                {state === "created"
                  ? "Created mail.template and active ir.cron."
                  : "Created mail.template only. Schedule stayed off."}
              </p>
              <div className="rm-ids">
                <span>
                  Template <code data-testid="reminders-template-id">44</code>
                </span>
                <span>
                  Cron{" "}
                  <code data-testid="reminders-cron-id">
                    {state === "created" ? "91" : "none (schedule off)"}
                  </code>
                </span>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default function RemindersHarnessPage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm text-muted">Loading harness…</main>}>
      <RemindersHarnessInner />
    </Suspense>
  );
}
