"use client";

import { FormEvent } from "react";
import { AutomationActionKindSelect } from "@/components/AutomationActionKindSelect";
import { DomainBuilder } from "@/components/DomainBuilder";
import { ExplainThisButton } from "@/components/expert/ExplainThisButton";
import { ModelTierInline } from "@/components/ModelTierInline";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Card } from "@/components/ui/layout-primitives";
import { Disclosure } from "@/components/ui/Disclosure";
import { Input } from "@/components/ui/Input";
import type {
  ActivityTypeRow,
  AutomationActionKind,
  Connection,
  ModelRow,
} from "@/lib/api";
import {
  ADVANCED_ACTION_KINDS,
  LIBRARY_FINE_SNIPPET,
  TRIGGER_GROUPS,
  TRIGGERS,
  triggerHint,
  type AutomationComposerForm,
} from "@/lib/automationForm";
import { AutomationActionFields } from "./AutomationActionFields";

type MailTemplate = {
  id: number;
  name: string;
  model: string | null;
  subject: string | null;
};

type AutomationComposerProps = {
  connectionId: string;
  connection: Connection | null;
  form: AutomationComposerForm;
  onChange: (patch: Partial<AutomationComposerForm>) => void;
  onSubmit: (e: FormEvent) => void;
  busy: boolean;
  canSubmit: boolean;
  supportedTriggers: Set<string> | null;
  activityTypes: ActivityTypeRow[];
  mailTemplates: MailTemplate[];
  models: ModelRow[];
};

export function AutomationComposer({
  connectionId,
  connection,
  form,
  onChange,
  onSubmit,
  busy,
  canSubmit,
  supportedTriggers,
  activityTypes,
  mailTemplates,
  models,
}: AutomationComposerProps) {
  const triggerBlocked =
    supportedTriggers != null && !supportedTriggers.has(form.trigger);
  const timed = form.trigger === "on_time";
  const valueChange =
    form.trigger === "on_write" ||
    form.trigger === "on_create_or_write" ||
    form.trigger === "on_change";
  const submitLabel = busy
    ? "Working…"
    : form.action_kind === "python_module"
      ? "Generate module zip"
      : ADVANCED_ACTION_KINDS.has(form.action_kind)
        ? "Create advanced automation"
        : "Create automation";

  return (
    <form
      data-testid="automations-form"
      onSubmit={onSubmit}
      className="space-y-4"
    >
      <Card className="space-y-4 p-5">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
            Trigger
          </p>
          <h2 className="text-base font-semibold text-ink">When this happens</h2>
        </div>
        <Input
          label="Rule name"
          required
          value={form.name}
          onChange={(e) => onChange({ name: e.target.value })}
          placeholder="Set status when created"
        />
        <div className="space-y-1.5">
          <label htmlFor="automation-model" className="block text-sm font-medium text-ink">
            Model
          </label>
          <input
            id="automation-model"
            required
            list="automation-model-options"
            value={form.model}
            onChange={(e) => onChange({ model: e.target.value })}
            className="h-9 w-full rounded-md border border-border-subtle bg-surface px-3 font-mono text-sm text-ink outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
            placeholder="res.partner"
          />
          <datalist id="automation-model-options">
            {models.map((m) => (
              <option key={m.model} value={m.model}>
                {m.name}
              </option>
            ))}
          </datalist>
          <p className="text-xs text-muted">Technical name. Type to search installed models.</p>
          <ModelTierInline connectionId={connectionId} model={form.model} />
        </div>
        <div className="space-y-1.5">
          <label htmlFor="automation-trigger" className="block text-sm font-medium text-ink">
            Trigger
          </label>
          <select
            id="automation-trigger"
            data-testid="automation-trigger"
            value={form.trigger}
            onChange={(e) => onChange({ trigger: e.target.value })}
            className="h-9 w-full rounded-md border border-border-subtle bg-surface px-3 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
          >
            {TRIGGER_GROUPS.map((group) => (
              <optgroup key={group.id} label={group.label}>
                {TRIGGERS.filter(
                  (t) =>
                    t.group === group.id &&
                    (!supportedTriggers || supportedTriggers.has(t.value)),
                ).map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
          <p className="text-xs text-muted">{triggerHint(form.trigger)}</p>
        </div>
        <ExplainThisButton
          question={`Explain automation trigger "${form.trigger}" for model ${form.model}`}
          label="Explain triggers"
        />
        {triggerBlocked ? (
          <Callout variant="warning" title="Trigger not supported on this Odoo">
            This trigger is not in the safe trigger set for this connection. Choose a
            supported trigger or export as a module.
          </Callout>
        ) : null}
        {timed ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <Input
              label="Date field"
              required
              value={form.trg_date_field_name}
              onChange={(e) => onChange({ trg_date_field_name: e.target.value })}
              className="font-mono text-sm"
              hint="Date or datetime on this model."
            />
            <Input
              label="Delay"
              type="number"
              min={0}
              value={form.trg_date_range}
              onChange={(e) => onChange({ trg_date_range: Number(e.target.value) || 0 })}
            />
            <SelectLike
              label="Unit"
              value={form.trg_date_range_type}
              onChange={(v) =>
                onChange({
                  trg_date_range_type: v as AutomationComposerForm["trg_date_range_type"],
                })
              }
              options={[
                { value: "minutes", label: "Minutes" },
                { value: "hour", label: "Hours" },
                { value: "day", label: "Days" },
                { value: "month", label: "Months" },
              ]}
            />
            <SelectLike
              label="When"
              value={form.trg_date_range_mode}
              onChange={(v) =>
                onChange({
                  trg_date_range_mode: v as AutomationComposerForm["trg_date_range_mode"],
                })
              }
              options={[
                { value: "after", label: "After the date" },
                { value: "before", label: "Before the date" },
              ]}
            />
          </div>
        ) : null}
        {valueChange ? (
          <Input
            label="When these fields change"
            value={form.trigger_field_names}
            onChange={(e) => onChange({ trigger_field_names: e.target.value })}
            className="font-mono text-sm"
            placeholder="x_status, x_stage_id"
            hint="Optional. Leave empty to run on any write (or any UI change)."
          />
        ) : null}
      </Card>

      <Card className="space-y-4 p-5">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
            Condition
          </p>
          <h2 className="text-base font-semibold text-ink">Apply on</h2>
        </div>
        <DomainBuilder
          label="Apply on"
          hint="Records must match this domain for the action to run."
          value={form.filter_domain || "[]"}
          onChange={(filter_domain) =>
            onChange({
              filter_domain: filter_domain === "[]" ? "" : filter_domain,
            })
          }
        />
        <Disclosure title="Before-update domain">
          <DomainBuilder
            label="Before update"
            hint="Evaluated on the record before the write. Use with On update for was-X-then-Y rules."
            value={form.filter_pre_domain || "[]"}
            onChange={(filter_pre_domain) =>
              onChange({
                filter_pre_domain: filter_pre_domain === "[]" ? "" : filter_pre_domain,
              })
            }
          />
        </Disclosure>
        <Disclosure title="Examples">
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() =>
                onChange({
                  name: form.name || "Vehicle rented on confirm",
                  model: "x_rental_contract",
                  trigger: "on_write",
                  filter_domain: "[('x_status', '=', 'confirmed')]",
                  action_kind: "related_write",
                  relation_field: "x_vehicle_id",
                  field_name: "x_status",
                  value: "rented",
                })
              }
            >
              Load car rental example
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() =>
                onChange({
                  name: form.name || "Library fine on return",
                  model: "x_lib_loan",
                  trigger: "on_write",
                  filter_domain: "[('x_returned', '=', True)]",
                  action_kind: "python_module",
                  python_code: LIBRARY_FINE_SNIPPET,
                  module_technical_name: "library_fine_on_return",
                })
              }
            >
              Load library fine (Option A)
            </Button>
          </div>
        </Disclosure>
      </Card>

      <Card className="space-y-4 p-5">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
            Action
          </p>
          <h2 className="text-base font-semibold text-ink">Then do this</h2>
        </div>
        <div className="space-y-1.5">
          <label htmlFor="automation-action-kind" className="block text-sm font-medium text-ink">
            Action
          </label>
          <AutomationActionKindSelect
            id="automation-action-kind"
            connection={connection}
            value={form.action_kind}
            onChange={(action_kind: AutomationActionKind) => onChange({ action_kind })}
          />
          <p className="text-xs text-muted">
            Safe actions are the default. Python live and webhooks stay behind confirm.
          </p>
        </div>
        <AutomationActionFields
          form={form}
          onChange={onChange}
          activityTypes={activityTypes}
          mailTemplates={mailTemplates}
        />
      </Card>

      <Button
        type="submit"
        variant="primary"
        disabled={busy || !canSubmit}
        data-testid="automations-submit"
        loading={busy}
      >
        {submitLabel}
      </Button>
    </form>
  );
}

function SelectLike({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  const id = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-ink">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 w-full rounded-md border border-border-subtle bg-surface px-3 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
