"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  ConfirmationRequiredError,
  Connection,
  FieldRow,
  ModelRow,
  SnapshotRow,
  type RelatedPathOption,
} from "@/lib/api";
import { fallbackWidgetsForTtype, type WidgetOption } from "@/lib/widgetCatalog";
import {
  connectionSupports,
  injectStrategyCapabilityId,
} from "@/lib/capabilities";
import { ExplainThisButton } from "@/components/expert/ExplainThisButton";
import { CapabilityProbePanel } from "@/components/CapabilityProbePanel";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Callout } from "@/components/ui/Callout";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/layout-primitives";
import { Disclosure } from "@/components/ui/Disclosure";
import { Input } from "@/components/ui/Input";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { PropertyFieldsPanel } from "@/components/builder/PropertyFieldsPanel";
import { InvoicingConnectPanel } from "@/components/builder/InvoicingConnectPanel";
import { BuilderModelsList } from "@/components/builder/BuilderModelsList";
import { BuilderSessionBar } from "@/components/builder/BuilderSessionBar";
import { ListComposerShell } from "@/components/ui/ListComposerShell";
import { BuilderSnapshots } from "@/components/builder/BuilderSnapshots";
import { FieldComposer } from "@/components/builder/FieldComposer";
import { ModelComposer } from "@/components/builder/ModelComposer";
import { ModelDetail } from "@/components/builder/ModelDetail";
import { RelationalPairPanel } from "@/components/builder/RelationalPairPanel";
import { useSyncShellContext } from "@/lib/use-sync-shell-context";
import { FirstWriteInterstitial } from "@/components/shell/FirstWriteInterstitial";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { reportApiError } from "@/lib/api-error";
import { selectionRowsToString } from "@/components/SelectionEditor";
import {
  CONFIRM_PHRASE,
  composerSessionState,
  createdFieldNotice,
  createdModelNotice,
  defaultFieldForm,
  defaultModelForm,
  defaultO2mForm,
  FIELD_DELETE_RISKS,
  fieldFormFromRow,
  fieldSubmitPayload,
  isComposerDirty,
  isCustomTechnicalName,
  MODEL_DELETE_RISKS,
  needsCurrency,
  needsOnDelete,
  needsRelation,
  needsSelection,
  viewDesignerHref,
  type FieldComposerForm,
  type ModelComposerForm,
  type O2mComposerForm,
} from "@/lib/builderForm";

type PendingDelete =
  | { kind: "model"; model: string; risks: string[] }
  | { kind: "field"; fieldId: number; name: string; risks: string[] };

type BuilderPane = "new-model" | "model";

export default function BuilderPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [probing, setProbing] = useState(false);
  const [customModels, setCustomModels] = useState<ModelRow[]>([]);
  const [snapshots, setSnapshots] = useState<SnapshotRow[]>([]);
  const [modelFields, setModelFields] = useState<FieldRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [listLoading, setListLoading] = useState(true);
  const [fieldsLoading, setFieldsLoading] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null);
  const [confirmTyped, setConfirmTyped] = useState("");
  const [confirmMutateOpen, setConfirmMutateOpen] = useState(false);

  const [pane, setPane] = useState<BuilderPane>("new-model");
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [selectedModelLabel, setSelectedModelLabel] = useState("");
  const [selectedFieldId, setSelectedFieldId] = useState<number | null>(null);
  const [listQuery, setListQuery] = useState("");
  const [fieldQuery, setFieldQuery] = useState("");
  const [justCreatedModel, setJustCreatedModel] = useState(false);
  const [enableMailThread, setEnableMailThread] = useState(false);
  const [savedOnce, setSavedOnce] = useState(false);

  const [modelForm, setModelForm] = useState<ModelComposerForm>(() => defaultModelForm());
  const [modelBaseline, setModelBaseline] = useState<ModelComposerForm>(() => defaultModelForm());
  const [fieldForm, setFieldForm] = useState<FieldComposerForm>(() => defaultFieldForm());
  const [fieldBaseline, setFieldBaseline] = useState<FieldComposerForm>(() => defaultFieldForm());
  const [o2mForm, setO2mForm] = useState<O2mComposerForm>(() => defaultO2mForm());

  const [widgetOptions, setWidgetOptions] = useState<WidgetOption[]>([]);
  const [relatedPaths, setRelatedPaths] = useState<RelatedPathOption[]>([]);

  const activeModel = selectedModel || fieldForm.model;
  useSyncShellContext({ model: activeModel });

  const patchModel = useCallback((patch: Partial<ModelComposerForm>) => {
    setModelForm((f) => ({ ...f, ...patch }));
  }, []);
  const patchField = useCallback((patch: Partial<FieldComposerForm>) => {
    setFieldForm((f) => ({ ...f, ...patch }));
  }, []);
  const patchO2m = useCallback((patch: Partial<O2mComposerForm>) => {
    setO2mForm((f) => ({ ...f, ...patch }));
  }, []);

  const refresh = useCallback(async () => {
    const [conn, customs, snaps] = await Promise.all([
      api.getConnection(connectionId),
      api.listModels(connectionId, true),
      api.listSnapshots(connectionId).catch(() => [] as SnapshotRow[]),
    ]);
    setConnection(conn);
    setCustomModels(customs);
    setSnapshots(snaps);
  }, [connectionId]);

  async function loadFieldsForModel(model: string) {
    setFieldsLoading(true);
    try {
      const fields = await api.listFields(connectionId, model);
      setModelFields(fields.filter((f) => f.name.startsWith("x_")));
    } finally {
      setFieldsLoading(false);
    }
  }

  function openModel(model: string, label?: string, created = false) {
    setPane("model");
    setSelectedModel(model);
    setSelectedModelLabel(label || model);
    setSelectedFieldId(null);
    setJustCreatedModel(created);
    const nextField = defaultFieldForm(model);
    setFieldForm(nextField);
    setFieldBaseline(nextField);
    setO2mForm((f) => ({ ...f, parent_model: f.parent_model || model }));
    loadFieldsForModel(model).catch((err: Error) => setError(err.message));
  }

  function startNewModel() {
    setPane("new-model");
    setSelectedModel(null);
    setSelectedFieldId(null);
    setJustCreatedModel(false);
    setNotice(null);
    const fresh = defaultModelForm();
    setModelForm(fresh);
    setModelBaseline(fresh);
  }

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
    openModel(fromQuery);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- one-shot URL hydrate
  }, []);

  useEffect(() => {
    let cancelled = false;
    setWidgetOptions(fallbackWidgetsForTtype(fieldForm.ttype));
    api
      .listBuilderWidgets(connectionId, fieldForm.ttype)
      .then((rows) => {
        if (!cancelled && rows.length > 0) setWidgetOptions(rows);
      })
      .catch(() => {
        /* fallback catalog */
      });
    return () => {
      cancelled = true;
    };
  }, [connectionId, fieldForm.ttype]);

  useEffect(() => {
    if (!fieldForm.model) {
      setRelatedPaths([]);
      return;
    }
    let cancelled = false;
    api
      .listRelatedPaths(connectionId, fieldForm.model, 2)
      .then((rows) => {
        if (!cancelled) setRelatedPaths(rows);
      })
      .catch(() => {
        if (!cancelled) setRelatedPaths([]);
      });
    return () => {
      cancelled = true;
    };
  }, [connectionId, fieldForm.model]);

  const injectCap = injectStrategyCapabilityId(fieldForm.inject_strategy);
  const canInjectStrategy = connectionSupports(connection, injectCap);
  const editingField = selectedFieldId != null;
  const modelDirty = isComposerDirty(modelForm, modelBaseline);
  const fieldDirty = isComposerDirty(fieldForm, fieldBaseline);
  const sessionState =
    pane === "new-model"
      ? composerSessionState({ dirty: modelDirty, savedOnce })
      : composerSessionState({ dirty: fieldDirty, savedOnce });
  const submitHint =
    pane === "new-model" ? "Create model" : editingField ? "Save field" : "Create field";

  async function onCreateModel(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const created = await api.createModel(connectionId, {
        name: modelForm.name,
        model: modelForm.model,
        with_defaults: true,
        enable_mail_thread: modelForm.enable_mail_thread,
      });
      setNotice(
        createdModelNotice({
          model: created.model,
          mailRequested: modelForm.enable_mail_thread,
          mailEnabled: created.mail_thread_enabled,
          warnings: created.warnings,
        }),
      );
      setEnableMailThread(modelForm.enable_mail_thread);
      setSavedOnce(true);
      const reset = defaultModelForm();
      setModelForm(reset);
      setModelBaseline(reset);
      await refresh();
      openModel(created.model, modelForm.name || created.model, true);
    } catch (err) {
      reportApiError(err, setError, { fallback: "Create model failed", toast: true });
    } finally {
      setBusy(false);
    }
  }

  async function submitCreateField(opts?: {
    confirm_advanced?: boolean;
    confirm_phrase?: string;
  }) {
    const willInject = fieldForm.inject_into_views && canInjectStrategy;
    if (willInject && fieldForm.inject_strategy === "mutate" && !opts?.confirm_advanced) {
      setConfirmMutateOpen(true);
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const { selection, relatedPath } = fieldSubmitPayload(fieldForm);
      const created = await api.createField(connectionId, {
        model: fieldForm.model,
        name: fieldForm.name,
        field_description: fieldForm.field_description,
        ttype: fieldForm.ttype,
        required: fieldForm.required,
        readonly: fieldForm.readonly || Boolean(relatedPath),
        relation: needsRelation(fieldForm.ttype) ? fieldForm.relation || null : null,
        relation_field:
          fieldForm.ttype === "one2many" ? fieldForm.relation_field || null : null,
        selection,
        help: fieldForm.help || null,
        related: relatedPath,
        currency_field: needsCurrency(fieldForm.ttype) ? fieldForm.currency_field || null : null,
        on_delete: needsOnDelete(fieldForm.ttype) ? fieldForm.on_delete : null,
        inject_into_views: willInject,
        inject_strategy: willInject ? fieldForm.inject_strategy : "inherit",
        view_widget: fieldForm.view_widget || null,
        ...(willInject && fieldForm.inject_strategy === "mutate"
          ? {
              confirm_advanced: true,
              confirm_phrase: opts?.confirm_phrase || CONFIRM_PHRASE,
            }
          : {}),
      });
      setNotice(
        createdFieldNotice({
          name: created.name,
          model: fieldForm.model,
          injectedViewIds: created.injected_view_ids,
          wantedInject: fieldForm.inject_into_views,
          currencyFieldCreated: created.currency_field_created,
        }),
      );
      const next = {
        ...defaultFieldForm(fieldForm.model),
      };
      setFieldForm(next);
      setFieldBaseline(next);
      setSelectedFieldId(null);
      setSavedOnce(true);
      setJustCreatedModel(false);
      setConfirmMutateOpen(false);
      await loadFieldsForModel(fieldForm.model);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmMutateOpen(true);
        setError(`${err.warning} Type “${err.confirm_phrase}” and retry.`);
      } else {
        reportApiError(err, setError, { fallback: "Create field failed", toast: true });
      }
    } finally {
      setBusy(false);
    }
  }

  async function submitUpdateField() {
    if (selectedFieldId == null) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await api.updateField(connectionId, selectedFieldId, {
        field_description: fieldForm.field_description,
        help: fieldForm.help || null,
        required: fieldForm.required,
        readonly: fieldForm.readonly,
        tracking: fieldForm.tracking,
        selection: needsSelection(fieldForm.ttype)
          ? selectionRowsToString(fieldForm.selectionRows)
          : undefined,
      });
      setNotice(`Updated field ${updated.name} on ${fieldForm.model}.`);
      setFieldBaseline(fieldForm);
      setSavedOnce(true);
      await loadFieldsForModel(fieldForm.model);
    } catch (err) {
      reportApiError(err, setError, { fallback: "Update field failed", toast: true });
    } finally {
      setBusy(false);
    }
  }

  async function onSubmitField(e: FormEvent) {
    e.preventDefault();
    if (editingField) {
      await submitUpdateField();
      return;
    }
    await submitCreateField();
  }

  async function onCreateO2m(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await api.createRelationalPair(connectionId, {
        parent_model: o2mForm.parent_model,
        child_model: o2mForm.child_model,
        parent_o2m_name: o2mForm.parent_o2m_name,
        child_m2o_name: o2mForm.child_m2o_name,
        parent_o2m_string: o2mForm.parent_o2m_string,
        child_m2o_string: o2mForm.child_m2o_string,
        inject_into_views:
          o2mForm.inject_into_views && connectionSupports(connection, "view_inject_inherit"),
      });
      const bits = [
        res.m2o_created ? `M2O ${res.child_m2o_name}` : null,
        res.o2m_created ? `O2M ${res.parent_o2m_name}` : null,
      ].filter(Boolean);
      setNotice(
        `Link one2many: ${bits.join(" + ") || "no new fields"}` +
          (res.injected_view_ids.length
            ? ` · injected views ${res.injected_view_ids.join(", ")}`
            : "") +
          (res.warnings.length ? ` · ${res.warnings.join("; ")}` : ""),
      );
      if (o2mForm.parent_model) {
        await loadFieldsForModel(o2mForm.parent_model);
      }
    } catch (err) {
      reportApiError(err, setError, { fallback: "Relational pair failed", toast: true });
    } finally {
      setBusy(false);
    }
  }

  async function proceedDelete(mode: "deprecate" | "hard_delete" = "hard_delete") {
    if (!pendingDelete) return;
    if (mode === "hard_delete" && confirmTyped !== CONFIRM_PHRASE) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (pendingDelete.kind === "model") {
        const res = await api.deleteModel(connectionId, pendingDelete.model, {
          confirm_advanced: true,
          confirm_phrase: CONFIRM_PHRASE,
        });
        setNotice(
          `Deleted model ${res.model}` +
            (res.snapshot_id ? ` · snapshot ${res.snapshot_id.slice(0, 8)}…` : ""),
        );
        if (selectedModel === pendingDelete.model || fieldForm.model === pendingDelete.model) {
          startNewModel();
          setModelFields([]);
        }
      } else {
        const res = await api.deleteField(connectionId, pendingDelete.fieldId, {
          mode,
          confirm_advanced: true,
          confirm_phrase: mode === "hard_delete" ? CONFIRM_PHRASE : undefined,
        });
        if (res.mode === "deprecate") {
          setNotice(
            `Deprecated field → ${res.new_field_name ?? "x_deprecated_*"}` +
              (res.snapshot_id ? ` · snapshot ${res.snapshot_id.slice(0, 8)}…` : ""),
          );
        } else {
          setNotice(
            `Hard-deleted field #${res.field_id}` +
              (res.row_count != null ? ` · exported ${res.row_count} row(s)` : "") +
              (res.artifact_url
                ? ` · backup ${res.artifact_url}`
                : res.snapshot_id
                  ? ` · snapshot ${res.snapshot_id.slice(0, 8)}…`
                  : ""),
          );
        }
        if (res.mode === "hard_delete") {
          setModelFields((rows) => rows.filter((f) => f.id !== pendingDelete.fieldId));
          if (selectedFieldId === pendingDelete.fieldId) {
            setSelectedFieldId(null);
            const next = defaultFieldForm(fieldForm.model);
            setFieldForm(next);
            setFieldBaseline(next);
          }
        } else if (fieldForm.model) {
          await loadFieldsForModel(fieldForm.model);
        }
      }
      setPendingDelete(null);
      setConfirmTyped("");
      await refresh();
    } catch (err) {
      reportApiError(err, setError, { fallback: "Delete failed", toast: true });
    } finally {
      setBusy(false);
    }
  }

  function discardComposer() {
    if (pane === "new-model") {
      setModelForm(modelBaseline);
      return;
    }
    setFieldForm(fieldBaseline);
    setSelectedFieldId(null);
  }

  function onSelectField(row: FieldRow) {
    if (!isCustomTechnicalName(row.name) || !selectedModel) return;
    setJustCreatedModel(false);
    setSelectedFieldId(row.id);
    const next = fieldFormFromRow(row, selectedModel);
    setFieldForm(next);
    setFieldBaseline(next);
  }

  function onNewField() {
    const model = selectedModel || fieldForm.model;
    const next = defaultFieldForm(model);
    setJustCreatedModel(false);
    setSelectedFieldId(null);
    setFieldForm(next);
    setFieldBaseline(next);
  }

  async function onRollback(snapshotId: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await api.rollbackSnapshot(connectionId, snapshotId);
      setNotice(`Restored ${res.restored} #${res.id}`);
      await refresh();
      if (selectedModel) await loadFieldsForModel(selectedModel);
    } catch (err) {
      reportApiError(err, setError, { fallback: "Rollback failed", toast: true });
    } finally {
      setBusy(false);
    }
  }

  const selectedCustom = useMemo(
    () => customModels.find((m) => m.model === selectedModel) ?? null,
    [customModels, selectedModel],
  );
  const canDiscard = pane === "new-model" ? modelDirty : fieldDirty;

  return (
    <div className="mx-auto max-w-6xl" data-testid="builder-page">
      <PageHeader
        title="Models and fields"
        description={`${connection ? `${connection.name} · ${connection.server_version ?? ""}` : connectionId} · live metadata on this Odoo instance. Prefer a sandbox before production writes.`}
        actions={
          <>
            <Button variant="secondary" size="sm" asChild>
              <Link
                href={viewDesignerHref(connectionId, selectedModel || fieldForm.model)}
                data-testid="builder-header-designer"
              >
                Open in View Designer
              </Link>
            </Button>
            <ExplainThisButton
              question={`Explain creating an x_ model and custom fields on ${activeModel}`}
              label="Explain models"
            />
          </>
        }
      />
      <FirstWriteInterstitial connection={connection} />
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

      {error ? (
        <ErrorNotice message={error} className="mt-4" onRetry={() => void refresh()} />
      ) : null}
      {notice ? (
        <Callout variant="info" title="Notice" className="mt-4">
          {notice}
        </Callout>
      ) : null}

      {pendingDelete ? (
        <div
          className="mt-6 rounded-md border border-danger/40 bg-danger-subtle p-5"
          data-testid="builder-delete-confirm"
        >
          <h2 className="text-ui-title text-danger">Warning</h2>
          <p className="mt-2 text-sm text-muted">
            {pendingDelete.kind === "model"
              ? `Delete model ${pendingDelete.model}? This often cannot be fully undone.`
              : `Field ${pendingDelete.name}: deprecate (recommended) renames to x_deprecated_* and keeps data. Hard delete exports a CSV backup first, then drops the column.`}
          </p>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted">
            {pendingDelete.risks.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          <div className="mt-4 max-w-lg">
            <Input
              label={`For hard delete, type ${CONFIRM_PHRASE}`}
              value={confirmTyped}
              onChange={(e) => setConfirmTyped(e.target.value)}
            />
          </div>
          <div className="mt-4 flex flex-wrap gap-3">
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setPendingDelete(null);
                setConfirmTyped("");
              }}
            >
              Cancel
            </Button>
            {pendingDelete.kind === "field" ? (
              <Button
                type="button"
                variant="secondary"
                disabled={busy}
                onClick={() => proceedDelete("deprecate")}
              >
                Deprecate (recommended)
              </Button>
            ) : null}
            <Button
              type="button"
              variant="danger"
              disabled={
                busy ||
                (pendingDelete.kind === "model" && confirmTyped !== CONFIRM_PHRASE) ||
                (pendingDelete.kind === "field" && confirmTyped !== CONFIRM_PHRASE)
              }
              onClick={() => proceedDelete("hard_delete")}
            >
              {pendingDelete.kind === "field" ? "Hard delete" : "Proceed"}
            </Button>
          </div>
        </div>
      ) : null}

      <ListComposerShell
        list={
          <>
          <BuilderModelsList
            rows={customModels}
            loading={listLoading}
            selectedModel={pane === "model" ? selectedModel : null}
            query={listQuery}
            onQueryChange={setListQuery}
            onSelect={(row) => {
              setNotice(null);
              setSavedOnce(false);
              setEnableMailThread(false);
              openModel(row.model, row.name);
            }}
            onCreate={startNewModel}
            onOpenExisting={(model) => {
              setNotice(null);
              openModel(model);
            }}
          />
          <BuilderSnapshots
            connectionId={connectionId}
            snapshots={snapshots}
            busy={busy}
            onRollback={onRollback}
          />
          </>
        }
        detail={
          <>
          <BuilderSessionBar
            sessionState={sessionState}
            busy={busy}
            canDiscard={canDiscard}
            submitLabel={submitHint}
            onDiscard={discardComposer}
          />
          {pane === "new-model" ? (
            <ModelComposer
              form={modelForm}
              onChange={patchModel}
              onSubmit={onCreateModel}
              busy={busy}
            />
          ) : (
            <>
              <ModelDetail
                connectionId={connectionId}
                model={selectedModel || fieldForm.model}
                modelLabel={selectedModelLabel}
                customRow={selectedCustom}
                fields={modelFields}
                fieldsLoading={fieldsLoading}
                fieldQuery={fieldQuery}
                selectedFieldId={selectedFieldId}
                justCreated={justCreatedModel}
                enableMailThread={enableMailThread}
                busy={busy}
                onFieldQueryChange={setFieldQuery}
                onSelectField={onSelectField}
                onNewField={onNewField}
                onRemoveField={(row) =>
                  setPendingDelete({
                    kind: "field",
                    fieldId: row.id,
                    name: row.name,
                    risks: FIELD_DELETE_RISKS,
                  })
                }
                onDeleteModel={
                  selectedModel && isCustomTechnicalName(selectedModel)
                    ? () =>
                        setPendingDelete({
                          kind: "model",
                          model: selectedModel,
                          risks: MODEL_DELETE_RISKS,
                        })
                    : undefined
                }
              />
              <FieldComposer
                connectionId={connectionId}
                connection={connection}
                form={fieldForm}
                mode={editingField ? "edit" : "create"}
                onChange={patchField}
                onSubmit={onSubmitField}
                busy={busy}
                widgetOptions={widgetOptions}
                relatedPaths={relatedPaths}
              />
              <Disclosure title="Link one2many pair" testId="builder-o2m-disclosure">
                <RelationalPairPanel
                  form={o2mForm}
                  onChange={patchO2m}
                  onSubmit={onCreateO2m}
                  connection={connection}
                  busy={busy}
                />
              </Disclosure>
              <Disclosure title="Properties and invoicing" testId="builder-advanced-panels">
                <div className="space-y-6">
                  <PropertyFieldsPanel
                    connectionId={connectionId}
                    connection={connection}
                    defaultChildModel={fieldForm.model || o2mForm.child_model}
                  />
                  <InvoicingConnectPanel
                    connectionId={connectionId}
                    connection={connection}
                    defaultModel={fieldForm.model || o2mForm.parent_model}
                  />
                </div>
              </Disclosure>
            </>
          )}
          </>
        }
      />

      <ConfirmDialogV2
        open={confirmMutateOpen}
        riskLevel="danger"
        title="Mutate parent view arch"
        warning="Mutating parent view arch overwrites existing module XML. Prefer inherit (default) for interop with installed modules."
        risks={[
          "Parent ir.ui.view arch is rewritten in place",
          "Module upgrades may conflict or overwrite your change",
          "Harder to uninstall cleanly than an extension view",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setConfirmMutateOpen(false)}
        onConfirm={(phrase) =>
          void submitCreateField({
            confirm_advanced: true,
            confirm_phrase: phrase,
          })
        }
      />
    </div>
  );
}
