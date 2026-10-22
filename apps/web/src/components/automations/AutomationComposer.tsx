"use client";

import { FormEvent, useState } from "react";
import { AutomationActionKindSelect } from "@/components/AutomationActionKindSelect";
import { DomainBuilder } from "@/components/DomainBuilder";
import { ExplainThisButton } from "@/components/expert/ExplainThisButton";
import { ModelTierInline } from "@/components/ModelTierInline";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
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
  OPTION_A_PATH_STEPS,
  TRIGGER_GROUPS,
  TRIGGERS,
  coerceToOptionA,
  parseAutomationPrompt,
  triggerHint,
  type AutomationComposerForm,
} from "@/lib/automationForm";
import { AutomationActionFields } from "./AutomationActionFields";
import { AutomationsStateGuide } from "./AutomationsStateGuide";

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
  const [prompt, setPrompt] = useState("");
  const triggerBlocked =
    supportedTriggers != null && !supportedTriggers.has(form.trigger);
  const timed = form.trigger === "on_time";
  const valueChange =
    form.trigger === "on_write" ||
    form.trigger === "on_create_or_write" ||
    form.trigger === "on_change";
  const kind = coerceToOptionA(form.action_kind);
  const isOptionA = kind === "python_module";
  const isWebhook = kind === "webhook";
  const isOnline = connection?.capabilities?.hosting_hint === "online";
  const submitLabel = busy
    ? "Working…"
    : isOptionA
      ? "Generate module zip"
      : ADVANCED_ACTION_KINDS.has(kind)
        ? "Create advanced automation"
        : "Create automation";

  function applyPrompt() {
    const hints = parseAutomationPrompt(prompt);
    const patch: Partial<AutomationComposerForm> = {};
    if (hints.name) patch.name = hints.name;
    if (hints.model) patch.model = hints.model;
    if (hints.trigger) patch.trigger = hints.trigger;
    if (hints.action_kind) patch.action_kind = coerceToOptionA(hints.action_kind);
    if (Object.keys(patch).length) onChange(patch);
  }

  function setActionKind(next: AutomationActionKind) {
    onChange({ action_kind: coerceToOptionA(next) });
  }

  return (
    <form
      data-testid="automations-form"
      onSubmit={onSubmit}
      className="space-y-3"
    >
      <div className="au-prompt" data-testid="automations-prompt">
        <p className="au-prompt-label" id="automations-prompt-label">
          Describe the rule
        </p>
        <textarea
          id="automations-prompt-input"
          aria-labelledby="automations-prompt-label"
          data-testid="automations-prompt-input"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="On create of x_visitor_log, set x_checked_in to true"
          rows={3}
        />
        <div className="au-prompt-footer">
          <p className="au-prompt-hint">
            Fills name, model, trigger, and action locally. Python wording becomes custom code,
            never live code.
          </p>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={!prompt.trim()}
            onClick={applyPrompt}
            data-testid="automations-prompt-apply"
          >
            Apply to form
          </Button>
        </div>
      </div>

      <section className="au-panel" data-testid="automations-panel-trigger">
        <h2 className="au-panel-title">When this happens</h2>
        <p className="au-panel-sub">
          Name the rule, pick the model and trigger. Safe record events are the default path.
        </p>
        <div className="au-panel-body">
          <Input
            label="Rule name"
            required
            value={form.name}
            onChange={(e) => onChange({ name: e.target.value })}
            placeholder="Set status when created"
          />
          <div className="space-y-1.5">
            <label htmlFor="automation-model" className="block text-ui-label text-ink">
              Model
            </label>
            <input
              id="automation-model"
              required
              list="automation-model-options"
              value={form.model}
              onChange={(e) => onChange({ model: e.target.value })}
              className="h-row w-full rounded-md border border-border-subtle bg-surface px-3 font-mono text-ui-body text-ink outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
              placeholder="res.partner"
            />
            <datalist id="automation-model-options">
              {models.map((m) => (
                <option key={m.model} value={m.model}>
                  {m.name}
                </option>
              ))}
            </datalist>
            <p className="text-ui-meta text-muted">Technical name. Type to search installed models.</p>
            <ModelTierInline connectionId={connectionId} model={form.model} />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="automation-trigger" className="block text-ui-label text-ink">
              Trigger
            </label>
            <select
              id="automation-trigger"
              data-testid="automation-trigger"
              value={form.trigger}
              onChange={(e) => onChange({ trigger: e.target.value })}
              className="h-row w-full rounded-md border border-border-subtle bg-surface px-3 text-ui-body text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
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
            <p className="text-ui-meta text-muted">{triggerHint(form.trigger)}</p>
          </div>
          <ExplainThisButton
            question={`Explain automation trigger "${form.trigger}" for model ${form.model}`}
            label="Explain triggers"
          />
          {triggerBlocked ? (
            <AutomationsStateGuide
              tone="warning"
              testId="automations-trigger-blocked"
              guide={{
                title: "Trigger not supported on this Odoo",
                why: "This trigger is not in the safe trigger set for this connection.",
                next: "Choose a supported trigger, or export as a module (custom code).",
              }}
            />
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
        </div>
      </section>

      <section className="au-panel" data-testid="automations-panel-condition">
        <h2 className="au-panel-title">Apply on</h2>
        <p className="au-panel-sub">
          Records must match this domain for the action to run.
        </p>
        <div className="au-panel-body">
          <DomainBuilder
            label="Apply on"
            hint="Leave empty to match every record for this trigger."
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
                data-testid="automations-example-option-a"
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
                Load library fine (custom code)
              </Button>
            </div>
          </Disclosure>
        </div>
      </section>

      <section className="au-panel" data-testid="automations-panel-action">
        <h2 className="au-panel-title">Then do this</h2>
        <p className="au-panel-sub">
          Safe actions are the default. Webhooks need advanced confirmation. Python stays
          Custom code: module, test copy, then publish.
        </p>
        <div className="au-panel-body">
          <div className="space-y-1.5">
            <label htmlFor="automation-action-kind" className="block text-ui-label text-ink">
              Action
            </label>
            <AutomationActionKindSelect
              id="automation-action-kind"
              connection={connection}
              value={kind}
              onChange={setActionKind}
            />
          </div>

          {isOptionA ? (
            <AutomationsStateGuide
              tone="accent"
              testId="automations-option-a"
              guide={{
                title: "Custom code: module, then test copy, then publish",
                why: "state=code never runs live from this screen. The zip carries the Python.",
                next: isOnline
                  ? "Odoo Online cannot install authored Python. Export the module and promote on Odoo.sh or self-hosted."
                  : "Generate the zip, prove it in sandbox, then publish with a human confirmation.",
              }}
            >
              <ol className="au-option-a-steps" data-testid="automations-option-a-steps">
                {OPTION_A_PATH_STEPS.map((step) => (
                  <li key={step.title}>
                    <span>
                      <strong>{step.title}.</strong> {step.detail}
                    </span>
                  </li>
                ))}
              </ol>
            </AutomationsStateGuide>
          ) : null}

          {isWebhook ? (
            <AutomationsStateGuide
              tone="warning"
              testId="automations-webhook-confirm"
              guide={{
                title: "Webhook needs advanced confirmation",
                why: "Creating this rule POSTs record data to an external URL.",
                next: "Review the URL and payload fields, then confirm with the risk phrase on create.",
              }}
            />
          ) : null}

          {isOnline && isOptionA ? (
            <Callout variant="warning" title="Online honesty" className="mt-0">
              Approximate validation only. Live Python install is not available on Odoo Online.
            </Callout>
          ) : null}

          <AutomationActionFields
            form={{ ...form, action_kind: kind }}
            onChange={onChange}
            activityTypes={activityTypes}
            mailTemplates={mailTemplates}
          />
        </div>
      </section>

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
      <label htmlFor={id} className="block text-ui-label text-ink">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-row w-full rounded-md border border-border-subtle bg-surface px-3 text-ui-body text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
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
