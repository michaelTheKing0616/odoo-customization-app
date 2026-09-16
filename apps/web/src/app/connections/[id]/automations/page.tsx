"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { PageHeader } from "@/components/ui/layout-primitives";
import { CapabilityProbePanel } from "@/components/CapabilityProbePanel";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { GatingCallout } from "@/components/GatingCallout";
import {
  ActivityTypeRow,
  api,
  AutomationRow,
  ConfirmationRequiredError,
  AutomationsGateResponse,
  Connection,
  GatingChoiceId,
  MigrationAssist,
  ModelRow,
  ModuleExport,
  SnapshotRow,
} from "@/lib/api";
import { ExplainThisButton } from "@/components/expert/ExplainThisButton";
import { useSyncShellContext } from "@/lib/use-sync-shell-context";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { reportApiError } from "@/lib/api-error";
import {
  ADVANCED_ACTION_KINDS,
  ADVANCED_CONFIRM_COPY,
  CONFIRM_PHRASE,
  actionKindAvailable,
  composerSessionState,
  defaultComposerForm,
  designerHref,
  firstAvailableSafeActionKind,
  isComposerDirty,
  parseFieldValueLines,
  parseIdList,
  parseNameList,
  type AutomationComposerForm,
} from "@/lib/automationForm";
import { AutomationComposer } from "@/components/automations/AutomationComposer";
import { AutomationDetail } from "@/components/automations/AutomationDetail";
import { AutomationsList } from "@/components/automations/AutomationsList";
import { AutomationSessionBar } from "@/components/automations/AutomationSessionBar";
import { ListComposerShell } from "@/components/ui/ListComposerShell";
import { AutomationSnapshots } from "@/components/automations/AutomationSnapshots";

function isModuleExport(v: AutomationRow | ModuleExport): v is ModuleExport {
  return "content_base64" in v;
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
  const [models, setModels] = useState<ModelRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [confirmMode, setConfirmMode] = useState<ConfirmMode | null>(null);
  const [confirmWarning, setConfirmWarning] = useState("");
  const [pendingRisks, setPendingRisks] = useState<string[]>([]);
  const [confirmPhrase, setConfirmPhrase] = useState(CONFIRM_PHRASE);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [listQuery, setListQuery] = useState("");
  const [modelFilter, setModelFilter] = useState("");
  const [savedOnce, setSavedOnce] = useState(false);

  const [form, setForm] = useState<AutomationComposerForm>(() => defaultComposerForm());
  const [baseline, setBaseline] = useState<AutomationComposerForm>(() =>
    defaultComposerForm(),
  );
  const [mailTemplates, setMailTemplates] = useState<
    Array<{ id: number; name: string; model: string | null; subject: string | null }>
  >([]);
  const [automationsGate, setAutomationsGate] = useState<AutomationsGateResponse | null>(
    null,
  );
  const [gatingChoice, setGatingChoice] = useState<GatingChoiceId | null>(null);
  const [migrationAssist, setMigrationAssist] = useState<MigrationAssist | null>(null);

  useSyncShellContext({ model: form.model, triggerType: form.trigger });

  const patchForm = useCallback((next: Partial<AutomationComposerForm>) => {
    setForm((f) => ({ ...f, ...next }));
  }, []);

  const refresh = useCallback(async () => {
    setListError(null);
    const [conns, autos, types, snaps, gate, migration, modelRows] = await Promise.all([
      api.listConnections(),
      api.listAutomations(connectionId).catch((err: unknown) => {
        setListError(err instanceof Error ? err.message : "Could not load automations");
        return [] as AutomationRow[];
      }),
      api.listActivityTypes(connectionId).catch(() => [] as ActivityTypeRow[]),
      api.listSnapshots(connectionId).catch(() => [] as SnapshotRow[]),
      api.getAutomationsGate(connectionId).catch(() => null),
      api.getMigrationAssist(connectionId).catch(() => null),
      api.listModels(connectionId).catch(() => [] as ModelRow[]),
    ]);
    setConnection(conns.find((c) => c.id === connectionId) ?? null);
    setRows(autos);
    setActivityTypes(types);
    setSnapshots(snaps);
    setAutomationsGate(gate);
    setMigrationAssist(migration);
    setModels(modelRows);
    setForm((f) =>
      types[0] && !f.activity_type_id ? { ...f, activity_type_id: types[0].id } : f,
    );
    setBaseline((b) =>
      types[0] && !b.activity_type_id ? { ...b, activity_type_id: types[0].id } : b,
    );
  }, [connectionId]);

  useEffect(() => {
    setListLoading(true);
    refresh()
      .catch((err: Error) => setError(err.message))
      .finally(() => setListLoading(false));
  }, [refresh]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const fromQuery = new URLSearchParams(window.location.search).get("model");
    if (!fromQuery) return;
    setModelFilter(fromQuery);
    setForm((f) => ({ ...f, model: fromQuery }));
    setBaseline((b) => ({ ...b, model: fromQuery }));
  }, []);

  useEffect(() => {
    if (!connection) return;
    setForm((f) => {
      if (actionKindAvailable(connection, f.action_kind)) return f;
      return { ...f, action_kind: firstAvailableSafeActionKind(connection) };
    });
    setBaseline((b) => {
      if (actionKindAvailable(connection, b.action_kind)) return b;
      return { ...b, action_kind: firstAvailableSafeActionKind(connection) };
    });
  }, [connection]);

  useEffect(() => {
    if (form.action_kind !== "mail_post") return;
    void api
      .listMailTemplates(connectionId, form.model)
      .then((rows) => {
        setMailTemplates(rows);
        setForm((f) =>
          f.mail_template_id || !rows[0] ? f : { ...f, mail_template_id: rows[0].id },
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

  function discardComposer() {
    setForm(baseline);
    setSelectedId(null);
  }

  function startNew() {
    setSelectedId(null);
    setNotice(null);
  }

  async function submit(opts?: { confirm_advanced?: boolean; confirm_phrase?: string }) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const valueChange =
        form.trigger === "on_write" ||
        form.trigger === "on_create_or_write" ||
        form.trigger === "on_change";
      const created = await api.createAutomation(connectionId, {
        name: form.name,
        model: form.model,
        trigger: form.trigger,
        filter_domain: form.filter_domain || null,
        filter_pre_domain: form.filter_pre_domain || null,
        trigger_field_names: valueChange ? parseNameList(form.trigger_field_names) : [],
        trg_date_field_name:
          form.trigger === "on_time" ? form.trg_date_field_name : null,
        trg_date_range: form.trigger === "on_time" ? form.trg_date_range : undefined,
        trg_date_range_type:
          form.trigger === "on_time" ? form.trg_date_range_type : undefined,
        trg_date_range_mode:
          form.trigger === "on_time" ? form.trg_date_range_mode : undefined,
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
        setSavedOnce(true);
      }
      const next = { ...form, name: "" };
      setForm(next);
      setBaseline(next);
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
        if (selectedId === confirmMode.automationId) setSelectedId(null);
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

  const selected = rows.find((r) => r.id === selectedId) ?? null;
  const dirty = isComposerDirty(form, baseline);
  const sessionState = composerSessionState({ dirty, savedOnce });
  const submitHint =
    form.action_kind === "python_module"
      ? "Generate module zip"
      : ADVANCED_ACTION_KINDS.has(form.action_kind)
        ? "Create advanced automation"
        : "Create automation";

  function duplicateRow(row: AutomationRow) {
    patchForm({
      name: `${row.name} copy`,
      model: row.model,
      trigger: row.trigger,
      filter_domain: row.filter_domain || "",
    });
    setSelectedId(null);
    setNotice("Loaded into the composer as a new rule. Create to save it on Odoo.");
  }

  return (
    <div className="mx-auto max-w-6xl" data-testid="automations-page">
      <PageHeader
        title="Automations"
        description={`${connection?.name ?? connectionId} · Model, trigger, apply-on, then a safe action. Python stays Option A unless you confirm live code.`}
        actions={
          <>
            <Button variant="secondary" size="sm" asChild>
              <Link
                href={designerHref(connectionId, selected?.model || form.model)}
                data-testid="automations-designer-link"
              >
                Open in View Designer
              </Link>
            </Button>
            <ExplainThisButton
              question={`Explain automations for model ${form.model}`}
              label="Explain automations"
            />
          </>
        }
      />
      <p className="mt-2 text-sm text-muted">
        Form buttons live in View Designer. This screen is the model-level twin — same model
        query, same public ORM.
      </p>
      <VersionAwarenessBanner capabilities={connection?.capabilities} className="mt-4" />
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

      {error ? (
        <ErrorNotice message={error} className="mt-4" onRetry={() => void refresh()} />
      ) : null}
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

      <ListComposerShell
        list={
          <>
          {listError ? (
            <ErrorNotice
              message={listError}
              className="mb-4"
              onRetry={() => void refresh()}
            />
          ) : null}
          <AutomationsList
            rows={rows}
            loading={listLoading}
            selectedId={selectedId}
            modelFilter={modelFilter}
            query={listQuery}
            onQueryChange={setListQuery}
            onSelect={(row) => {
              setSelectedId(row.id);
              setNotice(null);
            }}
            onCreate={startNew}
          />
          <AutomationSnapshots
            connectionId={connectionId}
            snapshots={snapshots}
            busy={busy}
            onRollback={onRollback}
          />
          </>
        }
        detail={
          selected ? (
            <AutomationDetail
              key={selected.id}
              connectionId={connectionId}
              row={selected}
              busy={busy}
              onSave={async ({ name, filter_domain }) => {
                setBusy(true);
                setError(null);
                try {
                  await api.updateAutomation(connectionId, selected.id, {
                    name,
                    filter_domain,
                  });
                  setNotice(`Updated automation #${selected.id}`);
                  await refresh();
                } catch (err) {
                  reportApiError(err, setError, { fallback: "Update failed", toast: true });
                } finally {
                  setBusy(false);
                }
              }}
              onDuplicate={() => duplicateRow(selected)}
              onToggleActive={() => {
                if (selected.active) {
                  openConfirm(
                    {
                      kind: "deactivate",
                      automationId: selected.id,
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
                    .setAutomationActive(connectionId, selected.id, true)
                    .then(async () => {
                      setNotice(`Activated automation #${selected.id}`);
                      await refresh();
                    })
                    .catch((err: unknown) => {
                      reportApiError(err, setError, {
                        fallback: "Update failed",
                        toast: true,
                      });
                    })
                    .finally(() => setBusy(false));
                }
              }}
              onDelete={() =>
                openConfirm(
                  { kind: "delete", automationId: selected.id },
                  "Deleting an automation permanently removes the rule and its server actions.",
                  [
                    "Automation will no longer run on matching records",
                    "Server action side effects already applied are not undone",
                    "A snapshot is taken so definition restore may be possible",
                  ],
                )
              }
            />
          ) : (
            <>
              <AutomationSessionBar
                sessionState={sessionState}
                busy={busy}
                canDiscard={dirty}
                submitLabel={submitHint}
                onDiscard={discardComposer}
              />
              <AutomationComposer
                connectionId={connectionId}
                connection={connection}
                form={form}
                onChange={patchForm}
                onSubmit={onSubmit}
                busy={busy}
                canSubmit={canSubmitAutomation}
                supportedTriggers={supportedTriggers}
                activityTypes={activityTypes}
                mailTemplates={mailTemplates}
                models={models}
              />
            </>
          )
        }
      />

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
