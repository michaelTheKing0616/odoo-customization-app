"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Card, EmptyState, PageHeader } from "@/components/ui/layout-primitives";
import { EMPTY_STATES } from "@/lib/copy-guide";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { CapabilityProbePanel } from "@/components/CapabilityProbePanel";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { DomainBuilder } from "@/components/DomainBuilder";
import { GatingCallout } from "@/components/GatingCallout";
import {
  ActivityTypeRow,
  api,
  AutomationActionKind,
  AutomationRow,
  ConfirmationRequiredError,
  AutomationsGateResponse,
  Connection,
  GatingChoiceId,
  MigrationAssist,
  ModuleExport,
  SnapshotRow,
} from "@/lib/api";
import { AutomationActionKindSelect } from "@/components/AutomationActionKindSelect";
import { ModelTierInline } from "@/components/ModelTierInline";
import { ExplainThisButton } from "@/components/expert/ExplainThisButton";
import { useSyncShellContext } from "@/lib/use-sync-shell-context";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { reportApiError } from "@/lib/api-error";

const LIBRARY_FINE_SNIPPET = `# Library fine on return — Option A (state=code in generated module / sandbox).
# Available: env, model, record, records, time, datetime, dateutil, timezone, log, Warning
for record in records:
    if not record.x_returned or not record.x_due_date:
        continue
    today = datetime.date.today()
    due = record.x_due_date
    days = max((today - due).days, 0)
    rate = (record.x_book_id.x_fine_rate if record.x_book_id else 0.0) or 0.0
    record.write({
        'x_days_overdue': days,
        'x_fine_amount': float(days) * float(rate),
    })
`;

const TRIGGERS = [
  { value: "on_create", label: "On create" },
  { value: "on_write", label: "On update" },
  { value: "on_create_or_write", label: "On create and edit" },
  { value: "on_unlink", label: "On deletion" },
  { value: "on_archive", label: "On archived" },
  { value: "on_unarchive", label: "On unarchived" },
  { value: "on_time", label: "Based on date field" },
  { value: "on_time_created", label: "After creation" },
  { value: "on_time_updated", label: "After last update" },
  { value: "on_message_received", label: "On message received (email)" },
  { value: "on_message_sent", label: "On message sent (email)" },
  { value: "on_webhook", label: "On webhook (incoming)" },
  { value: "on_change", label: "On UI change" },
] as const;

const CONFIRM_PHRASE = "I understand the risks";

const ADVANCED_ACTION_KINDS = new Set<AutomationActionKind>([
  "code_live",
  "webhook",
  "sms",
  "followers",
  "remove_followers",
]);

const ADVANCED_CONFIRM_COPY: Record<
  string,
  { warning: string; risks: string[] }
> = {
  code_live: {
    warning: "Live Python executes immediately on this database.",
    risks: [
      "Live Python executes immediately on this database",
      "Can modify any data the Odoo user can access",
      "Undo restores automation definition — not business data side effects",
    ],
  },
  webhook: {
    warning: "Webhook automations POST record data to an external URL.",
    risks: [
      "May exfiltrate business data to a third party",
      "URL must be trusted; payloads can include selected fields",
      "Rollback removes the rule — not data already sent",
    ],
  },
  sms: {
    warning: "SMS automations send messages via the Odoo SMS provider.",
    risks: [
      "May incur carrier / IAP costs",
      "Messages go to phone numbers on matching records",
      "Rollback removes the rule — not messages already sent",
    ],
  },
  followers: {
    warning: "Follower automations change who follows records.",
    risks: [
      "Can subscribe partners without their explicit consent in-app",
      "May increase notification noise",
      "Rollback removes the rule — not follower links already added",
    ],
  },
  remove_followers: {
    warning: "Remove-followers automations unsubscribe partners from records.",
    risks: [
      "Users may stop receiving important notifications",
      "Hard to reverse at scale once applied",
      "Rollback removes the rule — not follower removals already done",
    ],
  },
};

function isModuleExport(v: AutomationRow | ModuleExport): v is ModuleExport {
  return "content_base64" in v;
}

function parseFieldValueLines(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq <= 0) continue;
    const key = line.slice(0, eq).trim();
    const value = line.slice(eq + 1).trim();
    if (key) out[key] = value;
  }
  return out;
}

function parseIdList(text: string): number[] {
  return text
    .split(/[\s,]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => Number(s))
    .filter((n) => Number.isFinite(n) && n > 0);
}

function parseNameList(text: string): string[] {
  return text
    .split(/[\s,]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

type ConfirmMode =
  | { kind: "create_advanced" }
  | { kind: "delete"; automationId: number }
  | { kind: "deactivate"; automationId: number; currentlyActive: boolean };

export default function AutomationsPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [probing, setProbing] = useState(false);
  const [rows, setRows] = useState<AutomationRow[]>([]);
  const [snapshots, setSnapshots] = useState<SnapshotRow[]>([]);
  const [activityTypes, setActivityTypes] = useState<ActivityTypeRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmMode, setConfirmMode] = useState<ConfirmMode | null>(null);
  const [confirmWarning, setConfirmWarning] = useState("");
  const [pendingRisks, setPendingRisks] = useState<string[]>([]);
  const [confirmPhrase, setConfirmPhrase] = useState(CONFIRM_PHRASE);

  const [form, setForm] = useState({
    name: "",
    model: "res.partner",
    trigger: "on_create",
    filter_domain: "",
    filter_pre_domain: "",
    action_kind: "update_field" as AutomationActionKind,
    field_name: "x_auto_note",
    value: "automated",
    relation_field: "x_vehicle_id",
    activity_type_id: 0,
    activity_summary: "Follow up",
    trg_date_field_name: "create_date",
    target_model: "mail.activity",
    field_values_text: "summary=Follow up\nnote=Created by automation",
    mail_template_id: 0 as number | "",
    mail_post_method: "email" as "email" | "comment" | "note",
    mail_subject: "",
    mail_body_html: "",
    mail_email_to: "",
    webhook_url: "",
    webhook_field_names: "",
    sms_template_id: 0 as number | "",
    sms_body: "",
    sms_method: "sms" as "sms" | "comment" | "note",
    partner_ids_text: "",
    followers_type: "specific" as "specific" | "generic",
    followers_partner_field_name: "",
    python_code:
      "# available: env, model, record, records, time, datetime, dateutil, timezone, log, Warning\nrecord.write({'x_auto_note': 'from code'})\n",
    module_technical_name: "custom_automation_code",
  });
  const [mailTemplates, setMailTemplates] = useState<
    Array<{ id: number; name: string; model: string | null; subject: string | null }>
  >([]);
  const [automationsGate, setAutomationsGate] = useState<AutomationsGateResponse | null>(
    null,
  );
  const [gatingChoice, setGatingChoice] = useState<GatingChoiceId | null>(null);
  const [migrationAssist, setMigrationAssist] = useState<MigrationAssist | null>(null);

  useSyncShellContext({ model: form.model, triggerType: form.trigger });

  const refresh = useCallback(async () => {
    const [conns, autos, types, snaps, gate, migration] = await Promise.all([
      api.listConnections(),
      api.listAutomations(connectionId),
      api.listActivityTypes(connectionId).catch(() => [] as ActivityTypeRow[]),
      api.listSnapshots(connectionId).catch(() => [] as SnapshotRow[]),
      api.getAutomationsGate(connectionId).catch(() => null),
      api.getMigrationAssist(connectionId).catch(() => null),
    ]);
    setConnection(conns.find((c) => c.id === connectionId) ?? null);
    setRows(autos);
    setActivityTypes(types);
    setSnapshots(snaps);
    setAutomationsGate(gate);
    setMigrationAssist(migration);
    setForm((f) =>
      types[0] && !f.activity_type_id
        ? { ...f, activity_type_id: types[0].id }
        : f,
    );
  }, [connectionId]);

  useEffect(() => {
    refresh().catch((err: Error) => setError(err.message));
  }, [refresh]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const fromQuery = new URLSearchParams(window.location.search).get("model");
    if (fromQuery) setForm((f) => ({ ...f, model: fromQuery }));
  }, []);

  useEffect(() => {
    if (form.action_kind !== "mail_post") return;
    void api
      .listMailTemplates(connectionId, form.model)
      .then((rows) => {
        setMailTemplates(rows);
        setForm((f) =>
          f.mail_template_id || !rows[0]
            ? f
            : { ...f, mail_template_id: rows[0].id },
        );
      })
      .catch(() => setMailTemplates([]));
  }, [connectionId, form.action_kind, form.model]);

  function downloadModule(mod: ModuleExport) {
    const bin = Uint8Array.from(atob(mod.content_base64), (c) => c.charCodeAt(0));
    const blob = new Blob([bin], { type: "application/zip" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = mod.filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  function openConfirm(
    mode: ConfirmMode,
    warning: string,
    risks: string[],
    phrase = CONFIRM_PHRASE,
  ) {
    setConfirmMode(mode);
    setConfirmWarning(warning);
    setPendingRisks(risks);
    setConfirmPhrase(phrase);
  }

  async function submit(opts?: { confirm_advanced?: boolean; confirm_phrase?: string }) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const created = await api.createAutomation(connectionId, {
        name: form.name,
        model: form.model,
        trigger: form.trigger,
        filter_domain: form.filter_domain || null,
        filter_pre_domain: form.filter_pre_domain || null,
        trg_date_field_name:
          form.trigger === "on_time" ? form.trg_date_field_name : null,
        action_kind: form.action_kind,
        field_name:
          form.action_kind === "update_field" || form.action_kind === "related_write"
            ? form.field_name
            : undefined,
        value:
          form.action_kind === "update_field" || form.action_kind === "related_write"
            ? form.value
            : undefined,
        relation_field:
          form.action_kind === "related_write" ? form.relation_field : undefined,
        activity_type_id:
          form.action_kind === "create_activity" ? form.activity_type_id : undefined,
        activity_summary: form.activity_summary,
        activity_user_type: "generic",
        activity_user_field_name: undefined,
        target_model:
          form.action_kind === "create_record" ? form.target_model : undefined,
        field_values:
          form.action_kind === "create_record"
            ? parseFieldValueLines(form.field_values_text)
            : undefined,
        mail_template_id:
          form.action_kind === "mail_post"
            ? form.mail_template_id === ""
              ? null
              : form.mail_template_id
            : undefined,
        mail_post_method:
          form.action_kind === "mail_post" ? form.mail_post_method : undefined,
        mail_subject:
          form.action_kind === "mail_post" ? form.mail_subject || null : undefined,
        mail_body_html:
          form.action_kind === "mail_post" ? form.mail_body_html || null : undefined,
        mail_email_to:
          form.action_kind === "mail_post" ? form.mail_email_to || null : undefined,
        webhook_url:
          form.action_kind === "webhook" ? form.webhook_url || null : undefined,
        webhook_field_names:
          form.action_kind === "webhook"
            ? parseNameList(form.webhook_field_names)
            : undefined,
        sms_template_id:
          form.action_kind === "sms"
            ? form.sms_template_id === "" || form.sms_template_id === 0
              ? null
              : form.sms_template_id
            : undefined,
        sms_body: form.action_kind === "sms" ? form.sms_body || null : undefined,
        sms_method: form.action_kind === "sms" ? form.sms_method : undefined,
        partner_ids:
          form.action_kind === "followers" || form.action_kind === "remove_followers"
            ? parseIdList(form.partner_ids_text)
            : undefined,
        followers_type:
          form.action_kind === "followers" ? form.followers_type : undefined,
        followers_partner_field_name:
          form.action_kind === "followers"
            ? form.followers_partner_field_name || null
            : undefined,
        python_code:
          form.action_kind === "python_module" || form.action_kind === "code_live"
            ? form.python_code
            : undefined,
        module_technical_name: form.module_technical_name,
        confirm_advanced: opts?.confirm_advanced,
        confirm_phrase: opts?.confirm_phrase,
      });

      if (isModuleExport(created)) {
        downloadModule(created);
        setNotice(created.note);
      } else {
        setNotice(
          `Created automation #${created.id}` +
            (created.snapshot_id ? ` · snapshot ${created.snapshot_id.slice(0, 8)}…` : ""),
        );
      }
      setForm((f) => ({ ...f, name: "" }));
      setConfirmMode(null);
      await refresh();
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        openConfirm(
          { kind: "create_advanced" },
          err.warning,
          err.risks.length
            ? err.risks
            : [
                "Runs with the connected Odoo user's privileges",
                "Side effects may not be fully undoable",
                "Prefer Option A (module zip + sandbox) when possible",
              ],
          err.confirm_phrase || CONFIRM_PHRASE,
        );
        setError("Advanced confirmation required — review risks and type the phrase.");
      } else {
        reportApiError(err, setError, { fallback: "Create failed", toast: true });
      }
    } finally {
      setBusy(false);
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (ADVANCED_ACTION_KINDS.has(form.action_kind)) {
      const copy = ADVANCED_CONFIRM_COPY[form.action_kind] ?? {
        warning: "This advanced automation requires confirmation.",
        risks: [
          "Runs with the connected Odoo user's privileges",
          "Side effects may not be fully undoable",
        ],
      };
      openConfirm({ kind: "create_advanced" }, copy.warning, copy.risks);
      return;
    }
    await submit();
  }

  async function onRollback(snapshotId: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await api.rollbackSnapshot(connectionId, snapshotId);
      setNotice(`Restored ${res.restored} #${res.id}`);
      await refresh();
    } catch (err) {
      reportApiError(err, setError, { fallback: "Rollback failed", toast: true });
    } finally {
      setBusy(false);
    }
  }

  async function proceedConfirm(phrase: string) {
    if (!confirmMode) return;

    if (confirmMode.kind === "delete") {
      setBusy(true);
      setError(null);
      try {
        const res = await api.deleteAutomation(connectionId, confirmMode.automationId, {
          confirm_advanced: true,
          confirm_phrase: phrase,
        });
        setNotice(
          `Deleted automation #${res.automation_id}` +
            (res.snapshot_id ? ` · snapshot ${res.snapshot_id.slice(0, 8)}…` : ""),
        );
        setConfirmMode(null);
        await refresh();
      } catch (err) {
        if (err instanceof ConfirmationRequiredError) {
          setConfirmWarning(err.warning);
          setPendingRisks(err.risks);
          setConfirmPhrase(err.confirm_phrase);
          setError("Confirmation rejected or required again.");
        } else {
          reportApiError(err, setError, { fallback: "Delete failed", toast: true });
        }
      } finally {
        setBusy(false);
      }
      return;
    }

    if (confirmMode.kind === "deactivate") {
      setBusy(true);
      setError(null);
      try {
        await api.setAutomationActive(
          connectionId,
          confirmMode.automationId,
          !confirmMode.currentlyActive,
        );
        setNotice(
          `${confirmMode.currentlyActive ? "Deactivated" : "Activated"} automation #${confirmMode.automationId}`,
        );
        setConfirmMode(null);
        await refresh();
      } catch (err) {
        reportApiError(err, setError, { fallback: "Update failed", toast: true });
      } finally {
        setBusy(false);
      }
      return;
    }

    await submit({
      confirm_advanced: true,
      confirm_phrase: phrase,
    });
  }

  const supportedTriggers = useMemo(() => {
    const supported = connection?.capabilities?.supported;
    if (!supported) return null;
    if (supported.includes("base_automation_safe_triggers")) return null;
    return new Set<string>();
  }, [connection]);

  const automationsBlocked = automationsGate != null && !automationsGate.automations.available;
  const canSubmitAutomation =
    !automationsBlocked ||
    (gatingChoice === "export_module" && form.action_kind === "python_module");

  return (
    <div className="mx-auto max-w-4xl" data-testid="automations-page">
      <PageHeader
        title="Automations"
        description={`${connection?.name ?? connectionId} · Safe actions by default. Python: Option A module export, or live code with Odoo-style confirmation.`}
      />
      <p className="mt-2 text-sm text-muted">
        Form-bound button actions (update field, next activity, mail post, smart buttons)
        live in the{" "}
        <Link
          href={
            form.model
              ? `/connections/${connectionId}/designer?model=${encodeURIComponent(form.model)}`
              : `/connections/${connectionId}/designer`
          }
          className="text-accent hover:underline"
        >
          Designer
        </Link>
        .
      </p>
      <VersionAwarenessBanner capabilities={connection?.capabilities} />
        <CapabilityProbePanel
          capabilities={connection?.capabilities}
          defaultOpen={false}
          className="mt-2"
          refreshing={probing}
          onRefresh={() => {
            void (async () => {
              setProbing(true);
              setError(null);
              try {
                const result = await api.probeConnection(connectionId);
                setConnection((prev) =>
                  prev
                    ? {
                        ...prev,
                        server_version: result.server_version,
                        capabilities: result.capabilities,
                      }
                    : prev,
                );
              } catch (err) {
                setError(err instanceof Error ? err.message : "Probe failed");
              } finally {
                setProbing(false);
              }
            })();
          }}
        />

        {error ? <ErrorNotice message={error} className="mt-4" /> : null}
        {notice ? (
          <Callout variant="info" title="Notice" className="mt-4">
            {notice}
          </Callout>
        ) : null}

        {automationsGate && !automationsGate.automations.available ? (
          <GatingCallout
            className="mt-6"
            gating={automationsGate.automations}
            selectedChoice={gatingChoice}
            onSelectChoice={setGatingChoice}
          />
        ) : null}
        {migrationAssist?.eligible ? (
          <Callout
            variant="info"
            title={migrationAssist.title}
            className="mt-4"
            testId="automations-migration-assist"
          >
            <p>{migrationAssist.body}</p>
            <p className="mt-2 text-xs text-muted">
              See{" "}
              <Link href={`/connections/${connectionId}`} className="text-accent hover:underline">
                connection hub → Export section
              </Link>{" "}
              for the full migration assist panel.
            </p>
          </Callout>
        ) : null}

        <form
          data-testid="automations-form"
          onSubmit={onSubmit}
          className="mt-8 space-y-4"
        >
          <Card className="space-y-4 p-6">
            <h2 className="text-lg font-semibold text-ink">1 · Trigger</h2>
            <Input
              label="Rule name"
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <Input
              label="Model"
              required
              value={form.model}
              onChange={(e) => setForm({ ...form, model: e.target.value })}
              className="font-mono text-sm"
            />
            <ModelTierInline connectionId={connectionId} model={form.model} />
            <Select
              label="When (trigger)"
              options={TRIGGERS.filter(
                (t) => !supportedTriggers || supportedTriggers.has(t.value),
              ).map((t) => ({ value: t.value, label: t.label }))}
              value={form.trigger}
              onChange={(e) => setForm({ ...form, trigger: e.target.value })}
            />
            <ExplainThisButton
              question={`Explain automation trigger "${form.trigger}" for model ${form.model}`}
              label="Explain triggers"
            />
            {supportedTriggers && !supportedTriggers.has(form.trigger) ? (
              <Callout variant="warning" title="Trigger not supported on this Odoo">
                This trigger is not in the safe trigger set for this connection. Choose a
                supported trigger or export as module (Option A).
              </Callout>
            ) : null}
            {form.trigger === "on_time" ? (
              <Input
                label="Date field"
                required
                value={form.trg_date_field_name}
                onChange={(e) =>
                  setForm({ ...form, trg_date_field_name: e.target.value })
                }
                className="font-mono text-sm"
              />
            ) : null}
          </Card>

          <p className="text-center text-sm text-muted" aria-hidden>
            ↓
          </p>

          <Card className="space-y-4 p-6">
            <h2 className="text-lg font-semibold text-ink">2 · Condition</h2>
            <DomainBuilder
              label="Filter domain (after trigger / apply on)"
              value={form.filter_domain || "[]"}
              onChange={(filter_domain) =>
                setForm({
                  ...form,
                  filter_domain: filter_domain === "[]" ? "" : filter_domain,
                })
              }
            />
            <p className="text-xs text-muted">
              Records must match this domain for the action to run. Use with On
              update to limit which writes fire the rule.
            </p>
            <DomainBuilder
              label="Before-update domain (filter_pre_domain, optional)"
              value={form.filter_pre_domain || "[]"}
              onChange={(filter_pre_domain) =>
                setForm({
                  ...form,
                  filter_pre_domain:
                    filter_pre_domain === "[]" ? "" : filter_pre_domain,
                })
              }
            />
            <p className="text-xs text-muted">
              Evaluated on the record <em>before</em> the write (Odoo{" "}
              <code className="text-accent">filter_pre_domain</code>). Useful
              for “when status was X, then became Y” rules.
            </p>
            <div className="rounded-md border border-border-subtle bg-surface-muted/50 p-3 text-sm">
              <p className="font-medium text-ink">Presets</p>
              <div className="mt-2 flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    setForm({
                      ...form,
                      name: form.name || "Vehicle → rented on confirm",
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
                  Car rental: vehicle → rented
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    setForm({
                      ...form,
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
                  Library fine on return
                </Button>
              </div>
              <p className="mt-1 text-xs text-muted">
                Loads Option A Python snippet + filter for returned loans. Export
                module zip, sandbox, then promote.
              </p>
            </div>
          </Card>

          <p className="text-center text-sm text-muted" aria-hidden>
            ↓
          </p>

          <Card className="space-y-4 p-6">
            <h2 className="text-lg font-semibold text-ink">3 · Action</h2>
            {form.action_kind === "python_module" ? (
              <Callout variant="warning" title="Option A — exports as module">
                Python runs only after module export, sandbox test, and explicit promote.
                Review generated code before installing on production.
              </Callout>
            ) : null}
            <fieldset className="space-y-3">
              <AutomationActionKindSelect
              connection={connection}
              value={form.action_kind}
              onChange={(action_kind) => setForm({ ...form, action_kind })}
              className="w-full border border-border-subtle bg-surface px-3 py-2 text-sm"
            />

            {form.action_kind === "related_write" && (
              <>
                <label className="block text-sm">
                  <span className="text-[#a8909e]">Relation field (Many2one on this model)</span>
                  <input
                    required
                    value={form.relation_field}
                    onChange={(e) =>
                      setForm({ ...form, relation_field: e.target.value })
                    }
                    className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                    placeholder="x_vehicle_id"
                  />
                </label>
                <label className="block text-sm">
                  <span className="text-[#a8909e]">Field on related record</span>
                  <input
                    required
                    value={form.field_name}
                    onChange={(e) => setForm({ ...form, field_name: e.target.value })}
                    className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                    placeholder="x_status"
                  />
                </label>
                <label className="block text-sm">
                  <span className="text-[#a8909e]">Value</span>
                  <input
                    required
                    value={form.value}
                    onChange={(e) => setForm({ ...form, value: e.target.value })}
                    className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                    placeholder="rented"
                  />
                </label>
                <p className="text-xs text-muted">
                  Car rental example: on contract confirm → write{" "}
                  <code>x_vehicle_id.x_status = rented</code>.
                </p>
              </>
            )}

            {form.action_kind === "update_field" && (
              <>
                <label className="block text-sm">
                  <span className="text-[#a8909e]">Field name</span>
                  <input
                    required
                    value={form.field_name}
                    onChange={(e) => setForm({ ...form, field_name: e.target.value })}
                    className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                  />
                </label>
                <label className="block text-sm">
                  <span className="text-[#a8909e]">Value</span>
                  <input
                    required
                    value={form.value}
                    onChange={(e) => setForm({ ...form, value: e.target.value })}
                    className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2"
                  />
                </label>
              </>
            )}

            {form.action_kind === "create_activity" && (
              <>
                <label className="block text-sm">
                  <span className="text-[#a8909e]">Activity type</span>
                  <select
                    required
                    value={form.activity_type_id}
                    onChange={(e) =>
                      setForm({ ...form, activity_type_id: Number(e.target.value) })
                    }
                    className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2"
                  >
                    {activityTypes.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-sm">
                  <span className="text-[#a8909e]">Summary</span>
                  <input
                    required
                    value={form.activity_summary}
                    onChange={(e) =>
                      setForm({ ...form, activity_summary: e.target.value })
                    }
                    className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2"
                  />
                </label>
              </>
            )}

            {form.action_kind === "create_record" && (
              <>
                <label className="block text-sm">
                  <span className="text-[#a8909e]">Target model</span>
                  <input
                    required
                    value={form.target_model}
                    onChange={(e) => setForm({ ...form, target_model: e.target.value })}
                    className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                    placeholder="mail.activity"
                  />
                </label>
                <label className="block text-sm">
                  <span className="text-[#a8909e]">
                    Field values (one <code className="text-muted">key=value</code> per
                    line)
                  </span>
                  <textarea
                    rows={5}
                    value={form.field_values_text}
                    onChange={(e) =>
                      setForm({ ...form, field_values_text: e.target.value })
                    }
                    className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2 font-mono text-xs"
                    placeholder={"summary=Follow up\nnote=Hello"}
                  />
                </label>
              </>
            )}

            {form.action_kind === "mail_post" && (
              <>
                <label className="block text-sm">
                  <span className="text-[#a8909e]">Mail template (optional)</span>
                  <select
                    value={form.mail_template_id === "" ? "" : String(form.mail_template_id)}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        mail_template_id: e.target.value ? Number(e.target.value) : "",
                      })
                    }
                    className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2"
                  >
                    <option value="">None — use subject/body below</option>
                    {mailTemplates.map((t) => (
                      <option key={t.id} value={t.id}>
                        #{t.id} · {t.name}
                        {t.subject ? ` (${t.subject})` : ""}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-sm">
                  <span className="text-[#a8909e]">Post method</span>
                  <select
                    value={form.mail_post_method}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        mail_post_method: e.target.value as "email" | "comment" | "note",
                      })
                    }
                    className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2"
                  >
                    <option value="email">email</option>
                    <option value="comment">comment</option>
                    <option value="note">note</option>
                  </select>
                </label>
                <label className="block text-sm">
                  <span className="text-[#a8909e]">Subject</span>
                  <input
                    value={form.mail_subject}
                    onChange={(e) => setForm({ ...form, mail_subject: e.target.value })}
                    className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2"
                  />
                </label>
                <label className="block text-sm">
                  <span className="text-[#a8909e]">Email to</span>
                  <input
                    value={form.mail_email_to}
                    onChange={(e) => setForm({ ...form, mail_email_to: e.target.value })}
                    className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2"
                    placeholder="optional; template may set recipients"
                  />
                </label>
                <label className="block text-sm">
                  <span className="text-[#a8909e]">Body HTML</span>
                  <textarea
                    rows={5}
                    value={form.mail_body_html}
                    onChange={(e) => setForm({ ...form, mail_body_html: e.target.value })}
                    className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2 font-mono text-xs"
                  />
                </label>
              </>
            )}

            {form.action_kind === "webhook" && (
              <>
                <label className="block text-sm">
                  <span className="text-[#a8909e]">Webhook URL</span>
                  <input
                    required
                    type="url"
                    value={form.webhook_url}
                    onChange={(e) => setForm({ ...form, webhook_url: e.target.value })}
                    className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                    placeholder="https://example.com/hooks/odoo"
                  />
                </label>
                <label className="block text-sm">
                  <span className="text-[#a8909e]">
                    Payload fields (optional, comma-separated technical names)
                  </span>
                  <input
                    value={form.webhook_field_names}
                    onChange={(e) =>
                      setForm({ ...form, webhook_field_names: e.target.value })
                    }
                    className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                    placeholder="name, email, phone"
                  />
                </label>
              </>
            )}

            {form.action_kind === "sms" && (
              <>
                <label className="block text-sm">
                  <span className="text-[#a8909e]">SMS template id (optional)</span>
                  <input
                    type="number"
                    min={0}
                    value={form.sms_template_id === "" ? "" : form.sms_template_id}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        sms_template_id: e.target.value ? Number(e.target.value) : "",
                      })
                    }
                    className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                    placeholder="Leave empty to create from body"
                  />
                </label>
                <label className="block text-sm">
                  <span className="text-[#a8909e]">SMS body (if no template id)</span>
                  <textarea
                    rows={3}
                    value={form.sms_body}
                    onChange={(e) => setForm({ ...form, sms_body: e.target.value })}
                    className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2"
                    placeholder="Hello {{ object.name }}"
                  />
                </label>
                <label className="block text-sm">
                  <span className="text-[#a8909e]">SMS method</span>
                  <select
                    value={form.sms_method}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        sms_method: e.target.value as "sms" | "comment" | "note",
                      })
                    }
                    className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2"
                  >
                    <option value="sms">sms</option>
                    <option value="comment">comment</option>
                    <option value="note">note</option>
                  </select>
                </label>
              </>
            )}

            {(form.action_kind === "followers" ||
              form.action_kind === "remove_followers") && (
              <>
                <label className="block text-sm">
                  <span className="text-[#a8909e]">
                    Partner ids (optional, comma-separated)
                  </span>
                  <input
                    value={form.partner_ids_text}
                    onChange={(e) =>
                      setForm({ ...form, partner_ids_text: e.target.value })
                    }
                    className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                    placeholder="3, 7, 12"
                  />
                </label>
                {form.action_kind === "followers" && (
                  <>
                    <label className="block text-sm">
                      <span className="text-[#a8909e]">Followers type</span>
                      <select
                        value={form.followers_type}
                        onChange={(e) =>
                          setForm({
                            ...form,
                            followers_type: e.target.value as "specific" | "generic",
                          })
                        }
                        className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2"
                      >
                        <option value="specific">specific partners</option>
                        <option value="generic">generic (from field)</option>
                      </select>
                    </label>
                    {form.followers_type === "generic" && (
                      <label className="block text-sm">
                        <span className="text-[#a8909e]">Partner field name</span>
                        <input
                          required
                          value={form.followers_partner_field_name}
                          onChange={(e) =>
                            setForm({
                              ...form,
                              followers_partner_field_name: e.target.value,
                            })
                          }
                          className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                          placeholder="user_id.partner_id"
                        />
                      </label>
                    )}
                  </>
                )}
              </>
            )}

            {(form.action_kind === "python_module" ||
              form.action_kind === "code_live") && (
              <>
                {form.action_kind === "python_module" && (
                  <label className="block text-sm">
                    <span className="text-[#a8909e]">Module technical name</span>
                    <input
                      required
                      value={form.module_technical_name}
                      onChange={(e) =>
                        setForm({ ...form, module_technical_name: e.target.value })
                      }
                      className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                      pattern="[a-z][a-z0-9_]*"
                    />
                  </label>
                )}
                <label className="block text-sm">
                  <span className="text-[#a8909e]">Python code</span>
                  <textarea
                    required
                    rows={8}
                    value={form.python_code}
                    onChange={(e) => setForm({ ...form, python_code: e.target.value })}
                    className="mt-1 w-full border border-border-subtle bg-surface px-3 py-2 font-mono text-xs"
                  />
                </label>
              </>
            )}
          </fieldset>
          </Card>

          <Button
            type="submit"
            variant="primary"
            disabled={busy || !canSubmitAutomation}
            data-testid="automations-submit"
            loading={busy}
          >
            {busy
              ? "Working…"
              : form.action_kind === "python_module"
                ? "Generate module zip"
                : ADVANCED_ACTION_KINDS.has(form.action_kind)
                  ? "Create advanced automation…"
                  : "Create automation"}
          </Button>
        </form>

        <section className="mt-10">
          <h2 className="text-2xl font-semibold text-ink">Existing rules</h2>
          {rows.length === 0 ? (
            <div className="mt-4">
            <EmptyState
              title="No automations yet"
              description={EMPTY_STATES.automations}
            />
            </div>
          ) : (
          <ul className="mt-4 space-y-2 text-sm">
            {rows.map((r) => (
              <li key={r.id}>
                <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div>
                  <p className="font-medium text-ink">
                    #{r.id} {r.name}
                  </p>
                  <p className="text-muted">
                    {r.model} · {r.trigger} · {r.active ? "active" : "inactive"}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    disabled={busy}
                    onClick={() => {
                      if (r.active) {
                        openConfirm(
                          {
                            kind: "deactivate",
                            automationId: r.id,
                            currentlyActive: true,
                          },
                          "Deactivate this automation?",
                          [
                            "The rule will stop running on matching records",
                            "You can activate it again later",
                            "Already-applied side effects are not undone",
                          ],
                        );
                      } else {
                        setBusy(true);
                        setError(null);
                        api
                          .setAutomationActive(connectionId, r.id, true)
                          .then(async () => {
                            setNotice(`Activated automation #${r.id}`);
                            await refresh();
                          })
                          .catch((err: unknown) => {
                            setError(
                              err instanceof Error ? err.message : "Update failed",
                            );
                          })
                          .finally(() => setBusy(false));
                      }
                    }}
                  >
                    {r.active ? "Deactivate" : "Activate"}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={busy}
                    className="text-danger"
                    onClick={() =>
                      openConfirm(
                        { kind: "delete", automationId: r.id },
                        "Deleting an automation permanently removes the rule and its server actions.",
                        [
                          "Automation will no longer run on matching records",
                          "Server action side effects already applied are not undone",
                          "A snapshot is taken so definition restore may be possible",
                        ],
                      )
                    }
                  >
                    Delete
                  </Button>
                </div>
                </Card>
              </li>
            ))}
          </ul>
          )}
        </section>

        <section className="mt-10">
          <h2 className="text-2xl font-semibold text-ink">Snapshots / undo</h2>
          <p className="mt-1 text-sm text-muted">
            Restores definitions when possible. Does not rewind business data side effects.
          </p>
          <ul className="mt-4 space-y-2 text-sm">
            {snapshots.length === 0 && (
              <li className="text-muted">No snapshots yet.</li>
            )}
            {snapshots.map((s) => (
              <li key={s.id}>
                <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div>
                  <p className="text-ink">{s.label}</p>
                  <p className="text-muted">
                    {s.resource_type} · {s.reversible} · {s.created_at}
                  </p>
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={busy || s.reversible === "no"}
                  onClick={() => onRollback(s.id)}
                >
                  Undo
                </Button>
                </Card>
              </li>
            ))}
          </ul>
        </section>

      <ConfirmDialogV2
        open={confirmMode != null}
        riskLevel={
          confirmMode?.kind === "delete" || confirmMode?.kind === "deactivate"
            ? "danger"
            : "standard"
        }
        title="Warning"
        warning={confirmWarning}
        risks={pendingRisks}
        phrase={confirmPhrase}
        busy={busy}
        onCancel={() => setConfirmMode(null)}
        onConfirm={proceedConfirm}
      />
    </div>
  );
}
