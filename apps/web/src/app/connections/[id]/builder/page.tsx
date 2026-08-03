"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api, ConfirmationRequiredError, Connection, FieldRow, ModelRow } from "@/lib/api";
import {
  fallbackWidgetsForTtype,
  type WidgetOption,
} from "@/lib/widgetCatalog";
import {
  connectionSupports,
  connectionUnsupportedReason,
  currencyFieldSupported,
  currencyFieldUnsupportedReason,
  injectStrategyCapabilityId,
} from "@/lib/capabilities";
import { ExplainThisButton } from "@/components/expert/ExplainThisButton";
import {
  SelectionEditor,
  SelectionRow,
  selectionRowsToString,
} from "@/components/SelectionEditor";
import { CapabilityProbePanel } from "@/components/CapabilityProbePanel";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { PropertyFieldsPanel } from "@/components/builder/PropertyFieldsPanel";
import { InvoicingConnectPanel } from "@/components/builder/InvoicingConnectPanel";
import { useSyncShellContext } from "@/lib/use-sync-shell-context";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { reportApiError } from "@/lib/api-error";

const FIELD_TYPES = [
  "char",
  "text",
  "integer",
  "float",
  "boolean",
  "date",
  "datetime",
  "html",
  "binary",
  "selection",
  "many2one",
  "many2many",
  "one2many",
  "monetary",
  "json",
] as const;

const CONFIRM_PHRASE = "I understand the risks";

type PendingDelete =
  | { kind: "model"; model: string; risks: string[] }
  | { kind: "field"; fieldId: number; name: string; risks: string[] };

function slugifyTechnical(label: string, prefix = "x_"): string {
  const base = label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  const body = base || "custom";
  return body.startsWith("x_") ? body : `${prefix}${body}`;
}

export default function BuilderPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [probing, setProbing] = useState(false);
  const [customModels, setCustomModels] = useState<ModelRow[]>([]);
  const [modelFields, setModelFields] = useState<FieldRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null);
  const [confirmTyped, setConfirmTyped] = useState("");

  const [modelForm, setModelForm] = useState({
    name: "",
    model: "x_",
    enable_mail_thread: false,
  });

  const [o2mForm, setO2mForm] = useState({
    parent_model: "",
    child_model: "",
    parent_o2m_name: "x_line_ids",
    child_m2o_name: "x_parent_id",
    parent_o2m_string: "Lines",
    child_m2o_string: "Parent",
    inject_into_views: true,
  });

  const [fieldForm, setFieldForm] = useState({
    model: "res.partner",
    name: "x_",
    field_description: "",
    ttype: "char",
    required: false,
    readonly: false,
    relation: "",
    relation_field: "",
    selectionRows: [
      { value: "draft", label: "Draft" },
      { value: "done", label: "Done" },
    ] as SelectionRow[],
    help: "",
    related: "",
    currency_field: "currency_id",
    on_delete: "restrict" as "set null" | "restrict" | "cascade",
    inject_into_views: true,
    inject_strategy: "inherit" as "inherit" | "mutate",
    view_widget: "",
  });

  const [widgetOptions, setWidgetOptions] = useState<WidgetOption[]>([]);
  const [relatedPaths, setRelatedPaths] = useState<
    { path: string; label: string; ttype: string }[]
  >([]);

  const [createdFields, setCreatedFields] = useState<FieldRow[]>([]);
  const [confirmMutateOpen, setConfirmMutateOpen] = useState(false);

  useSyncShellContext({ model: fieldForm.model });

  const refresh = useCallback(async () => {
    const [conns, customs] = await Promise.all([
      api.listConnections(),
      api.listModels(connectionId, true),
    ]);
    setConnection(conns.find((c) => c.id === connectionId) ?? null);
    setCustomModels(customs);
  }, [connectionId]);

  async function loadFieldsForModel(model: string) {
    const fields = await api.listFields(connectionId, model);
    setModelFields(fields.filter((f) => f.name.startsWith("x_")));
  }

  useEffect(() => {
    refresh().catch((err: Error) => setError(err.message));
  }, [refresh]);

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

  const needsRelation = useMemo(
    () => ["many2one", "many2many", "one2many"].includes(fieldForm.ttype),
    [fieldForm.ttype],
  );
  const needsOnDelete = fieldForm.ttype === "many2one";
  const needsSelection = fieldForm.ttype === "selection";
  const hasRelatedPath = Boolean(fieldForm.related.trim());
  const needsCurrency = fieldForm.ttype === "monetary";
  const injectCap = injectStrategyCapabilityId(fieldForm.inject_strategy);
  const canInjectStrategy = connectionSupports(connection, injectCap);

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
      const mailNote = modelForm.enable_mail_thread
        ? created.mail_thread_enabled
          ? " Mail thread flag set on ir.model."
          : ` Chatter: ${(created.warnings || []).join(" ") || "export mixins for full chatter."}`
        : "";
      setNotice(
        `Created model ${created.model} with x_name, default list/form/search views, and Internal User ACL.${mailNote}`,
      );
      setFieldForm((f) => ({ ...f, model: created.model }));
      setO2mForm((f) => ({
        ...f,
        parent_model: f.parent_model || created.model,
      }));
      setModelForm({ name: "", model: "x_", enable_mail_thread: false });
      await refresh();
      await loadFieldsForModel(created.model);
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
    if (
      willInject &&
      fieldForm.inject_strategy === "mutate" &&
      !opts?.confirm_advanced
    ) {
      setConfirmMutateOpen(true);
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const selection = needsSelection
        ? fieldForm.selectionRows
            .filter((r) => r.value.trim())
            .map((r) => ({
              value: r.value.trim(),
              label: (r.label.trim() || r.value).trim(),
            }))
        : null;

      const relatedPath = fieldForm.related.trim() || null;
      const created = await api.createField(connectionId, {
        model: fieldForm.model,
        name: fieldForm.name,
        field_description: fieldForm.field_description,
        ttype: fieldForm.ttype,
        required: fieldForm.required,
        readonly: fieldForm.readonly || Boolean(relatedPath),
        relation: needsRelation ? fieldForm.relation || null : null,
        relation_field:
          fieldForm.ttype === "one2many" ? fieldForm.relation_field || null : null,
        selection,
        help: fieldForm.help || null,
        related: relatedPath,
        currency_field: needsCurrency ? fieldForm.currency_field || null : null,
        on_delete: needsOnDelete ? fieldForm.on_delete : null,
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
      setCreatedFields((rows) => [created, ...rows]);
      const injected =
        created.injected_view_ids?.length > 0
          ? ` Injected into view(s) ${created.injected_view_ids.join(", ")}.`
          : fieldForm.inject_into_views
            ? " (no existing form/list/search to inject into)"
            : "";
      const currencyNote = created.currency_field_created
        ? ` Auto-created currency field ${created.currency_field_created}.`
        : "";
      setNotice(
        `Created field ${created.name} on ${fieldForm.model}.${injected}${currencyNote}`,
      );
      setFieldForm((f) => ({
        ...f,
        name: "x_",
        field_description: "",
        help: "",
        related: "",
      }));
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

  async function onCreateField(e: FormEvent) {
    e.preventDefault();
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
          o2mForm.inject_into_views &&
          connectionSupports(connection, "view_inject_inherit"),
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

  async function proceedDelete() {
    if (!pendingDelete || confirmTyped !== CONFIRM_PHRASE) return;
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
        if (fieldForm.model === pendingDelete.model) {
          setFieldForm((f) => ({ ...f, model: "res.partner" }));
          setModelFields([]);
        }
      } else {
        const res = await api.deleteField(connectionId, pendingDelete.fieldId, {
          confirm_advanced: true,
          confirm_phrase: CONFIRM_PHRASE,
        });
        setNotice(
          `Deleted field #${res.field_id}` +
            (res.snapshot_id ? ` · snapshot ${res.snapshot_id.slice(0, 8)}…` : ""),
        );
        setCreatedFields((rows) => rows.filter((f) => f.id !== pendingDelete.fieldId));
        setModelFields((rows) => rows.filter((f) => f.id !== pendingDelete.fieldId));
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

  return (
    <main className="min-h-screen bg-[radial-gradient(ellipse_at_top,_#3d2a38_0%,_#1a1218_50%,_#0c090b_100%)] px-6 py-10 text-[#f4eef2]">
      <div className="mx-auto max-w-5xl">
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <Link href={`/connections/${connectionId}`} className="text-[#c9a9c0] hover:underline">
            ← Metadata
          </Link>
          <Link href="/connect" className="text-[#8f7a88] hover:underline">
            Connections
          </Link>
          <Link
            href={`/connections/${connectionId}/reminders`}
            className="text-[#8f7a88] hover:underline"
          >
            Reminders
          </Link>
        </div>
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl text-[#faf6f9]">
          Model & field builder
        </h1>
        <p className="mt-1 text-sm text-[#8f7a88]">
          {connection
            ? `${connection.name} · ${connection.server_version ?? ""}`
            : connectionId}
          {" · "}
          writes live metadata to Odoo (sandbox instance recommended)
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
        {notice && <p className="mt-4 text-sm text-[#c9a9c0]">{notice}</p>}

        {pendingDelete && (
          <div className="mt-6 border border-[#a85b4a] bg-[#2a1512] p-5">
            <h2 className="font-[family-name:var(--font-display)] text-xl text-[#f0a8a0]">
              Warning
            </h2>
            <p className="mt-2 text-sm text-[#e8cfc9]">
              {pendingDelete.kind === "model"
                ? `Delete model ${pendingDelete.model}? This often cannot be fully undone.`
                : `Delete field ${pendingDelete.name}? Column data may be unrestorable.`}
            </p>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-[#e8cfc9]">
              {pendingDelete.risks.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
            <label className="mt-4 block text-sm">
              <span className="text-[#e8cfc9]">
                Type <code className="text-[#f0a8a0]">{CONFIRM_PHRASE}</code> to continue
              </span>
              <input
                value={confirmTyped}
                onChange={(e) => setConfirmTyped(e.target.value)}
                className="mt-1 w-full border border-[#5a3a36] bg-[#0c090b] px-3 py-2"
              />
            </label>
            <div className="mt-4 flex gap-3">
              <button
                type="button"
                className="border border-[#8f7a88] px-4 py-2 text-sm"
                onClick={() => {
                  setPendingDelete(null);
                  setConfirmTyped("");
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={busy || confirmTyped !== CONFIRM_PHRASE}
                className="bg-[#a85b4a] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                onClick={() => proceedDelete()}
              >
                Proceed
              </button>
            </div>
          </div>
        )}

        <div className="mt-10 grid gap-8 lg:grid-cols-2">
          <form
            onSubmit={onCreateModel}
            className="space-y-4 border border-[#3d2a38] bg-[#0f1a16]/70 p-6"
          >
            <h2 className="font-[family-name:var(--font-display)] text-xl">
              New model
            </h2>
            <p className="text-sm text-[#8f7a88]">
              Creates an <code className="text-[#c9a9c0]">x_*</code> model,{" "}
              <code className="text-[#c9a9c0]">x_name</code>, and default
              list/form/search views.
            </p>
            <label className="block text-sm">
              <span className="text-[#a8909e]">Label</span>
              <input
                required
                value={modelForm.name}
                onChange={(e) => {
                  const name = e.target.value;
                  setModelForm((prev) => ({
                    ...prev,
                    name,
                    model: slugifyTechnical(name),
                  }));
                }}
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
                placeholder="Project Ticket"
              />
            </label>
            <label className="block text-sm">
              <span className="text-[#a8909e]">Technical name</span>
              <input
                required
                value={modelForm.model}
                onChange={(e) =>
                  setModelForm({ ...modelForm, model: e.target.value })
                }
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                pattern="x_[a-z0-9_]+"
              />
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={modelForm.enable_mail_thread}
                onChange={(e) =>
                  setModelForm({
                    ...modelForm,
                    enable_mail_thread: e.target.checked,
                  })
                }
              />
              <span>
                <span className="text-[#a8909e]">Chatter &amp; activities (mail)</span>
                <span className="mt-0.5 block text-xs text-[#8f7a88]">
                  Ensures mail is installed; full chatter needs Python export with
                  mail.thread mixins.
                </span>
              </span>
            </label>
            <button
              type="submit"
              disabled={busy}
              className="h-11 bg-[#714B67] px-5 text-sm font-semibold text-white disabled:opacity-60"
            >
              Create model
            </button>

            {customModels.length > 0 && (
              <div className="pt-4">
                <p className="text-xs uppercase tracking-wide text-[#8f7a88]">
                  Custom models on this instance
                </p>
                <ul className="mt-2 max-h-48 space-y-2 overflow-auto text-sm">
                  {customModels.map((m) => (
                    <li
                      key={m.id}
                      className="flex flex-wrap items-center justify-between gap-2 border border-[#1e2f29] px-2 py-1.5"
                    >
                      <button
                        type="button"
                        className="text-left text-[#c9a9c0] hover:underline"
                        onClick={() => {
                          setFieldForm((f) => ({ ...f, model: m.model }));
                          loadFieldsForModel(m.model).catch((err: Error) =>
                            setError(err.message),
                          );
                        }}
                      >
                        {m.name}{" "}
                        <span className="font-mono text-[#8f7a88]">{m.model}</span>
                      </button>
                      <button
                        type="button"
                        disabled={busy}
                        className="text-xs text-[#f0a8a0] hover:underline disabled:opacity-50"
                        onClick={() =>
                          setPendingDelete({
                            kind: "model",
                            model: m.model,
                            risks: [
                              "Often irreversible — tables/data may not restore",
                              "Dependent views and automations can break",
                              "Snapshot stores definition only (partial)",
                            ],
                          })
                        }
                      >
                        Delete
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </form>

          <form
            onSubmit={onCreateField}
            className="space-y-4 border border-[#3d2a38] bg-[#0f1a16]/70 p-6"
          >
            <h2 className="font-[family-name:var(--font-display)] text-xl">
              New field
            </h2>
            <label className="block text-sm">
              <span className="text-[#a8909e]">Target model</span>
              <input
                required
                value={fieldForm.model}
                onChange={(e) =>
                  setFieldForm({ ...fieldForm, model: e.target.value })
                }
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                placeholder="res.partner or x_…"
              />
            </label>
            <label className="block text-sm">
              <span className="text-[#a8909e]">Label</span>
              <input
                required
                value={fieldForm.field_description}
                onChange={(e) => {
                  const field_description = e.target.value;
                  setFieldForm({
                    ...fieldForm,
                    field_description,
                    name: slugifyTechnical(field_description),
                  });
                }}
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
              />
            </label>
            <label className="block text-sm">
              <span className="text-[#a8909e]">Technical name</span>
              <input
                required
                value={fieldForm.name}
                onChange={(e) =>
                  setFieldForm({ ...fieldForm, name: e.target.value })
                }
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                pattern="x_[A-Za-z0-9_]+"
              />
            </label>
            <label className="block text-sm">
              <span className="flex items-center gap-1 text-[#a8909e]">
                Type
                <ExplainThisButton
                  question={`Explain many2one vs many2many vs one2many for a new field on ${fieldForm.model}`}
                  label="Explain field types"
                />
              </span>
              <select
                value={fieldForm.ttype}
                onChange={(e) =>
                  setFieldForm({ ...fieldForm, ttype: e.target.value })
                }
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
              >
                {FIELD_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </label>

            {needsRelation && (
              <label className="block text-sm">
                <span className="text-[#a8909e]">Relation model</span>
                <input
                  required
                  value={fieldForm.relation}
                  onChange={(e) =>
                    setFieldForm({ ...fieldForm, relation: e.target.value })
                  }
                  className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                  placeholder="res.partner"
                />
              </label>
            )}
            {fieldForm.ttype === "one2many" && (
              <label className="block text-sm">
                <span className="text-[#a8909e]">Relation field</span>
                <input
                  required
                  value={fieldForm.relation_field}
                  onChange={(e) =>
                    setFieldForm({ ...fieldForm, relation_field: e.target.value })
                  }
                  className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                  placeholder="x_parent_id"
                />
              </label>
            )}
            {needsOnDelete && (
              <label className="block text-sm">
                <span className="text-[#a8909e]">On delete</span>
                <select
                  value={fieldForm.on_delete}
                  onChange={(e) =>
                    setFieldForm({
                      ...fieldForm,
                      on_delete: e.target.value as
                        | "set null"
                        | "restrict"
                        | "cascade",
                    })
                  }
                  className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
                >
                  <option value="restrict">restrict</option>
                  <option value="cascade">cascade</option>
                  <option value="set null">set null</option>
                </select>
                <span className="mt-1 block text-xs text-[#8f7a88]">
                  Odoo 19: required many2one cannot use set null — prefer restrict.
                </span>
              </label>
            )}
            {needsSelection && (
              <div className="block text-sm">
                <span className="text-[#a8909e]">Selection options</span>
                <div className="mt-1">
                  <SelectionEditor
                    value={fieldForm.selectionRows}
                    onChange={(selectionRows) =>
                      setFieldForm({ ...fieldForm, selectionRows })
                    }
                  />
                </div>
                <p className="mt-1 text-xs text-[#8f7a88]">
                  Serialized:{" "}
                  <code className="text-[#c9a9c0]">
                    {selectionRowsToString(fieldForm.selectionRows)}
                  </code>
                </p>
              </div>
            )}
            {widgetOptions.length > 0 && (
              <label className="block text-sm">
                <span className="text-[#a8909e]">Form widget hint</span>
                <select
                  value={fieldForm.view_widget}
                  onChange={(e) =>
                    setFieldForm({
                      ...fieldForm,
                      view_widget: e.target.value,
                    })
                  }
                  className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
                >
                  <option value="">Default</option>
                  {widgetOptions.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.label}
                    </option>
                  ))}
                </select>
                <span className="mt-1 block text-xs text-[#8f7a88]">
                  When injecting into form views, sets{" "}
                  <code className="text-[#c9a9c0]">widget=&quot;…&quot;</code> on the field.
                </span>
              </label>
            )}
            <label className="block text-sm">
              <span className="text-[#a8909e]">Related path (optional)</span>
              {relatedPaths.length > 0 ? (
                <select
                  value={fieldForm.related}
                  onChange={(e) =>
                    setFieldForm({ ...fieldForm, related: e.target.value })
                  }
                  className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                >
                  <option value="">— none —</option>
                  {relatedPaths.map((p) => (
                    <option key={p.path} value={p.path}>
                      {p.label} ({p.path})
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  value={fieldForm.related}
                  onChange={(e) =>
                    setFieldForm({ ...fieldForm, related: e.target.value })
                  }
                  className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                  placeholder="partner_id.country_id"
                />
              )}
              <span className="mt-1 block text-xs text-[#8f7a88]">
                When set, Odoo stores a readonly related field using the type above
                (there is no ttype=related).
              </span>
            </label>
            {needsCurrency && (
              <div className="space-y-2">
                <label className="block text-sm">
                  <span className="text-[#a8909e]">Currency field</span>
                  <input
                    value={fieldForm.currency_field}
                    onChange={(e) =>
                      setFieldForm({ ...fieldForm, currency_field: e.target.value })
                    }
                    className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                    placeholder="currency_id"
                  />
                </label>
                {!currencyFieldSupported(connection) && (
                  <p className="text-xs text-[#e8d09f]">
                    {currencyFieldUnsupportedReason(connection)}
                  </p>
                )}
              </div>
            )}

            <div className="flex flex-wrap gap-4 text-sm">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={fieldForm.required}
                  onChange={(e) =>
                    setFieldForm({ ...fieldForm, required: e.target.checked })
                  }
                />
                Required
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={fieldForm.readonly || hasRelatedPath}
                  disabled={hasRelatedPath}
                  onChange={(e) =>
                    setFieldForm({ ...fieldForm, readonly: e.target.checked })
                  }
                />
                Readonly
              </label>
              <label
                className="flex items-center gap-2"
                title={
                  connectionUnsupportedReason(connection, injectCap) ?? undefined
                }
              >
                <input
                  type="checkbox"
                  checked={fieldForm.inject_into_views && canInjectStrategy}
                  disabled={!canInjectStrategy}
                  onChange={(e) =>
                    setFieldForm({
                      ...fieldForm,
                      inject_into_views: e.target.checked,
                    })
                  }
                />
                Inject into form/list/search
              </label>
            </div>
            <label className="block text-sm">
              <span className="text-[#a8909e]">Inject strategy</span>
              <select
                value={fieldForm.inject_strategy}
                onChange={(e) =>
                  setFieldForm({
                    ...fieldForm,
                    inject_strategy: e.target.value as "inherit" | "mutate",
                  })
                }
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 text-sm"
              >
                <option
                  value="inherit"
                  disabled={!connectionSupports(connection, "view_inject_inherit")}
                >
                  inherit (xpath child)
                  {!connectionSupports(connection, "view_inject_inherit")
                    ? " — unavailable"
                    : ""}
                </option>
                <option
                  value="mutate"
                  disabled={!connectionSupports(connection, "view_inject_mutate")}
                >
                  mutate (overwrite parent)
                  {!connectionSupports(connection, "view_inject_mutate")
                    ? " — unavailable"
                    : ""}
                </option>
              </select>
            </label>
            {!canInjectStrategy && (
              <p className="text-xs text-[#e8d09f]">
                {connectionUnsupportedReason(connection, injectCap)}
              </p>
            )}
            {fieldForm.inject_strategy === "mutate" &&
              connectionSupports(connection, "view_inject_mutate") && (
                <p className="text-xs text-[#e8d09f]">
                  Mutate overwrites parent view arch — requires advanced confirm on
                  create.
                </p>
              )}

            <button
              type="submit"
              disabled={busy}
              className="h-11 bg-[#714B67] px-5 text-sm font-semibold text-white disabled:opacity-60"
            >
              Create field
            </button>

            {(modelFields.length > 0 || createdFields.length > 0) && (
              <ul className="space-y-1 pt-2 text-sm text-[#d4c4ce]">
                {(modelFields.length > 0 ? modelFields : createdFields).map((f) => (
                  <li
                    key={f.id}
                    className="flex flex-wrap items-center justify-between gap-2"
                  >
                    <span>
                      <span className="font-mono text-[#c9a9c0]">{f.name}</span> ·{" "}
                      {f.ttype} · {f.field_description}
                    </span>
                    {f.name.startsWith("x_") && (
                      <button
                        type="button"
                        disabled={busy}
                        className="text-xs text-[#f0a8a0] hover:underline disabled:opacity-50"
                        onClick={() =>
                          setPendingDelete({
                            kind: "field",
                            fieldId: f.id,
                            name: f.name,
                            risks: [
                              "Dropped columns / field data may be unrestorable",
                              "Views referencing the field can break",
                              "Snapshot stores definition only (partial)",
                            ],
                          })
                        }
                      >
                        Delete
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </form>
        </div>

        <form
          onSubmit={onCreateO2m}
          className="mt-8 space-y-4 border border-[#3d2a38] bg-[#0f1a16]/70 p-6"
        >
          <h2 className="font-[family-name:var(--font-display)] text-xl">
            Link one2many
          </h2>
          <p className="text-sm text-[#8f7a88]">
            Creates a required M2O on the child (on_delete=restrict) and an O2M on
            the parent pointing at it — e.g. Book → Loans.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="text-[#a8909e]">Parent model</span>
              <input
                required
                value={o2mForm.parent_model}
                onChange={(e) =>
                  setO2mForm({ ...o2mForm, parent_model: e.target.value })
                }
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                placeholder="x_lib_book"
              />
            </label>
            <label className="block text-sm">
              <span className="text-[#a8909e]">Child model</span>
              <input
                required
                value={o2mForm.child_model}
                onChange={(e) =>
                  setO2mForm({ ...o2mForm, child_model: e.target.value })
                }
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                placeholder="x_lib_loan"
              />
            </label>
            <label className="block text-sm">
              <span className="text-[#a8909e]">Parent O2M name</span>
              <input
                required
                value={o2mForm.parent_o2m_name}
                onChange={(e) =>
                  setO2mForm({ ...o2mForm, parent_o2m_name: e.target.value })
                }
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
              />
            </label>
            <label className="block text-sm">
              <span className="text-[#a8909e]">Child M2O name</span>
              <input
                required
                value={o2mForm.child_m2o_name}
                onChange={(e) =>
                  setO2mForm({ ...o2mForm, child_m2o_name: e.target.value })
                }
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
              />
            </label>
            <label className="block text-sm">
              <span className="text-[#a8909e]">Parent O2M label</span>
              <input
                required
                value={o2mForm.parent_o2m_string}
                onChange={(e) =>
                  setO2mForm({ ...o2mForm, parent_o2m_string: e.target.value })
                }
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
              />
            </label>
            <label className="block text-sm">
              <span className="text-[#a8909e]">Child M2O label</span>
              <input
                required
                value={o2mForm.child_m2o_string}
                onChange={(e) =>
                  setO2mForm({ ...o2mForm, child_m2o_string: e.target.value })
                }
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
              />
            </label>
          </div>
          <label
            className="flex items-center gap-2 text-sm"
            title={
              connectionUnsupportedReason(connection, "view_inject_inherit") ??
              undefined
            }
          >
            <input
              type="checkbox"
              checked={
                o2mForm.inject_into_views &&
                connectionSupports(connection, "view_inject_inherit")
              }
              disabled={!connectionSupports(connection, "view_inject_inherit")}
              onChange={(e) =>
                setO2mForm({ ...o2mForm, inject_into_views: e.target.checked })
              }
            />
            Inject O2M into parent form
          </label>
          <button
            type="submit"
            disabled={busy}
            className="h-11 bg-[#714B67] px-5 text-sm font-semibold text-white disabled:opacity-60"
          >
            Create relational pair
          </button>
        </form>
      </div>

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

      <InvoicingConnectPanel
        connectionId={connectionId}
        connection={connection}
        defaultModel={fieldForm.model || o2mForm.parent_model}
      />

      <ConfirmDialog
        open={confirmMutateOpen}
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
    </main>
  );
}
