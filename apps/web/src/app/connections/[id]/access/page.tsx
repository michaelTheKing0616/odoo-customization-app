"use client";

import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  AccessMatrixOut,
  AccessRightRow,
  api,
  Connection,
  GroupRow,
  RecordRuleRow,
} from "@/lib/api";
import { DomainBuilder } from "@/components/DomainBuilder";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import {
  advancedMutationAllowed,
  advancedMutationBlockedReason,
  mutationAllowed,
  mutationBlockedReason,
} from "@/lib/capabilities";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Card, PageHeader } from "@/components/ui/layout-primitives";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Tabs } from "@/components/ui/Tabs";

const CONFIRM_PHRASE = "I understand the risks";

type PendingDelete =
  | { kind: "access"; id: number; name: string; risks: string[] }
  | { kind: "rule"; id: number; name: string; risks: string[] };

export default function AccessPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [model, setModel] = useState("res.partner");
  const [groups, setGroups] = useState<GroupRow[]>([]);
  const [rights, setRights] = useState<AccessRightRow[]>([]);
  const [rules, setRules] = useState<RecordRuleRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null);
  const [matrixModels, setMatrixModels] = useState("res.partner");
  const [matrix, setMatrix] = useState<AccessMatrixOut | null>(null);
  const [matrixBusy, setMatrixBusy] = useState(false);
  const [mcGuidance, setMcGuidance] = useState<{ title: string; body: string } | null>(
    null,
  );
  const [docsGate, setDocsGate] = useState<{
    available: boolean;
    message?: string | null;
  } | null>(null);
  const [docsFolders, setDocsFolders] = useState<
    Array<{ id: number; name: string | null }>
  >([]);
  const [docsFolderId, setDocsFolderId] = useState("");
  const [docsMapping, setDocsMapping] = useState<Record<string, number>>({});

  const [accessForm, setAccessForm] = useState({
    name: "",
    group_id: "",
    perm_read: true,
    perm_write: true,
    perm_create: true,
    perm_unlink: false,
  });

  const [ruleForm, setRuleForm] = useState({
    name: "",
    domain_force: "[('create_uid', '=', user.id)]",
    group_id: "",
    perm_read: true,
    perm_write: true,
    perm_create: true,
    perm_unlink: true,
  });

  const refresh = useCallback(
    async (target: string) => {
      const [conns, gs, rs, rls] = await Promise.all([
        api.listConnections(),
        api.listGroups(connectionId),
        api.listAccessRights(connectionId, target),
        api.listRecordRules(connectionId, target),
      ]);
      setConnection(conns.find((c) => c.id === connectionId) ?? null);
      setGroups(gs);
      setRights(rs);
      setRules(rls);
    },
    [connectionId],
  );

  useEffect(() => {
    refresh("res.partner").catch((err: Error) => setError(err.message));
    api.getMultiCompanyGuidance(connectionId).then(setMcGuidance).catch(() => {});
    api
      .getDocumentsGate(connectionId)
      .then((g) => setDocsGate({ available: g.available, message: g.message }))
      .catch(() => setDocsGate({ available: false }));
    api
      .getDocumentsFolderMap(connectionId)
      .then((m) => setDocsMapping(m.mapping))
      .catch(() => {});
  }, [refresh, connectionId]);

  async function onLoadModel(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await refresh(model);
      setNotice(`Loaded access for ${model}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Load failed");
    } finally {
      setBusy(false);
    }
  }

  async function onCreateAccess(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const created = await api.createAccessRight(connectionId, {
        model,
        name: accessForm.name || `${model} access`,
        group_id: accessForm.group_id ? Number(accessForm.group_id) : null,
        perm_read: accessForm.perm_read,
        perm_write: accessForm.perm_write,
        perm_create: accessForm.perm_create,
        perm_unlink: accessForm.perm_unlink,
      });
      setNotice(`Created access #${created.id} for ${created.model}`);
      setAccessForm((f) => ({ ...f, name: "" }));
      await refresh(model);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create access failed");
    } finally {
      setBusy(false);
    }
  }

  async function onCreateRule(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const created = await api.createRecordRule(connectionId, {
        model,
        name: ruleForm.name || `${model} rule`,
        domain_force: ruleForm.domain_force,
        group_ids: ruleForm.group_id ? [Number(ruleForm.group_id)] : [],
        perm_read: ruleForm.perm_read,
        perm_write: ruleForm.perm_write,
        perm_create: ruleForm.perm_create,
        perm_unlink: ruleForm.perm_unlink,
      });
      setNotice(`Created record rule #${created.id}`);
      setRuleForm((f) => ({ ...f, name: "" }));
      await refresh(model);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create rule failed");
    } finally {
      setBusy(false);
    }
  }

  async function loadMatrix() {
    setMatrixBusy(true);
    setError(null);
    try {
      const models = matrixModels
        .split(",")
        .map((m) => m.trim())
        .filter(Boolean);
      const data = await api.accessMatrix(connectionId, models);
      setMatrix(data);
      setNotice(`Matrix loaded for ${data.models.length} model(s)`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Matrix load failed");
    } finally {
      setMatrixBusy(false);
    }
  }

  async function toggleMatrixPerm(
    cell: AccessMatrixOut["cells"][number],
    groupId: number | null,
    key: "perm_read" | "perm_write" | "perm_create" | "perm_unlink",
  ) {
    setMatrixBusy(true);
    setError(null);
    try {
      const next = !cell[key];
      if (cell.access_id) {
        await api.updateAccessRight(connectionId, cell.access_id, { [key]: next });
      } else {
        await api.createAccessRight(connectionId, {
          model: cell.model,
          name: `${cell.model} / group ${groupId ?? "all"}`,
          group_id: groupId,
          perm_read: key === "perm_read" ? next : false,
          perm_write: key === "perm_write" ? next : false,
          perm_create: key === "perm_create" ? next : false,
          perm_unlink: key === "perm_unlink" ? next : false,
        });
      }
      await loadMatrix();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
      setMatrixBusy(false);
    }
  }

  function cellFor(
    modelName: string,
    groupId: number | null,
  ): AccessMatrixOut["cells"][number] {
    const found = matrix?.cells.find(
      (c) =>
        c.model === modelName &&
        (c.group_id ?? null) === groupId &&
        c.active !== false,
    );
    return (
      found ?? {
        model: modelName,
        group_id: groupId,
        access_id: null,
        name: null,
        perm_read: false,
        perm_write: false,
        perm_create: false,
        perm_unlink: false,
        active: true,
      }
    );
  }

  async function proceedDelete() {
    if (!pendingDelete) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (pendingDelete.kind === "access") {
        const res = await api.deleteAccessRight(connectionId, pendingDelete.id, {
          confirm_advanced: true,
          confirm_phrase: CONFIRM_PHRASE,
        });
        setNotice(
          `Deleted access #${res.access_id}` +
            (res.snapshot_id ? ` · snapshot ${res.snapshot_id.slice(0, 8)}…` : ""),
        );
      } else {
        const res = await api.deleteRecordRule(connectionId, pendingDelete.id, {
          confirm_advanced: true,
          confirm_phrase: CONFIRM_PHRASE,
        });
        setNotice(
          `Deleted rule #${res.rule_id}` +
            (res.snapshot_id ? ` · snapshot ${res.snapshot_id.slice(0, 8)}…` : ""),
        );
      }
      setPendingDelete(null);
      await refresh(model);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  const canMutate = mutationAllowed(connection);
  const mutateBlocked = mutationBlockedReason(connection);
  const canAdvanced = advancedMutationAllowed(connection);
  const advancedBlocked = advancedMutationBlockedReason(connection);

  const rightsColumns: DataTableColumn<AccessRightRow>[] = [
    { id: "name", header: "Name", accessor: (r) => r.name },
    {
      id: "group",
      header: "Group",
      accessor: (r) => <span className="text-muted">{r.group_name ?? "(all)"}</span>,
    },
    {
      id: "crud",
      header: "CRUD",
      accessor: (r) => (
        <span className="font-mono text-xs">
          {[r.perm_read && "R", r.perm_write && "W", r.perm_create && "C", r.perm_unlink && "D"]
            .filter(Boolean)
            .join("") || "—"}
        </span>
      ),
    },
    {
      id: "actions",
      header: "",
      accessor: (r) => (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={busy || !canAdvanced}
          title={advancedBlocked ?? undefined}
          onClick={() =>
            setPendingDelete({
              kind: "access",
              id: r.id,
              name: r.name,
              risks: [
                "Users may lose or gain unintended access",
                "Can lock operators out of custom models if no other ACL remains",
                "Snapshot allows restoring the access line when possible",
              ],
            })
          }
        >
          Delete
        </Button>
      ),
    },
  ];

  return (
    <div className="mx-auto max-w-5xl" data-testid="access-page">
      <PageHeader
        title="Access rights"
        description={`${connection?.name ?? connectionId} · matrix, groups, ACL lines, record rules`}
      />
      <VersionAwarenessBanner capabilities={connection?.capabilities} />
      {mutateBlocked ? (
        <Callout variant="warning" title="Mutations blocked" className="mt-4">
          {mutateBlocked}
        </Callout>
      ) : null}
      {!mutateBlocked && advancedBlocked ? (
        <Callout variant="warning" title="Advanced mutations" className="mt-4">
          {advancedBlocked}
        </Callout>
      ) : null}

      <Tabs
        className="mt-6"
        defaultValue="matrix"
        items={[
          {
            value: "matrix",
            label: "Matrix",
            content: (
              <Card className="p-5">
                <h2 className="text-xl font-semibold text-ink">Access matrix</h2>
                <p className="mt-1 text-xs text-muted">
                  Groups × models. Click R/W/C/D to toggle. Empty cell creates a new access line.
                </p>
                <div className="mt-3 flex flex-wrap items-end gap-3">
                  <Input
                    label="Models (comma-separated)"
                    value={matrixModels}
                    onChange={(e) => setMatrixModels(e.target.value)}
                    className="w-full max-w-md font-mono"
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={matrixBusy}
                    loading={matrixBusy}
                    onClick={() => void loadMatrix()}
                  >
                    Load matrix
                  </Button>
                </div>
                {matrix ? (
                  <div className="mt-4 overflow-auto">
                    <table className="min-w-full text-left text-xs">
                      <thead className="text-muted">
                        <tr>
                          <th className="sticky left-0 bg-surface-raised py-2 pr-3">
                            Group \\ Model
                          </th>
                          {matrix.models.map((m) => (
                            <th key={m} className="px-2 py-2 font-mono">
                              {m}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {matrix.groups.slice(0, 40).map((g) => (
                          <tr key={g.id} className="border-t border-border-subtle">
                            <td className="sticky left-0 bg-surface-raised py-2 pr-3 text-accent">
                              {g.full_name || g.name}
                            </td>
                            {matrix.models.map((m) => {
                              const cell = cellFor(m, g.id);
                              return (
                                <td key={`${m}-${g.id}`} className="px-2 py-2">
                                  <div className="flex gap-1 font-mono">
                                    {(
                                      [
                                        ["perm_read", "R"],
                                        ["perm_write", "W"],
                                        ["perm_create", "C"],
                                        ["perm_unlink", "D"],
                                      ] as const
                                    ).map(([key, label]) => (
                                      <button
                                        key={key}
                                        type="button"
                                        disabled={matrixBusy || !canMutate}
                                        title={
                                          mutateBlocked ?? `${label} ${cell[key] ? "on" : "off"}`
                                        }
                                        onClick={() => void toggleMatrixPerm(cell, g.id, key)}
                                        className={`rounded px-1 ${
                                          cell[key]
                                            ? "bg-accent text-on-accent"
                                            : "border border-border-subtle text-muted"
                                        }`}
                                      >
                                        {label}
                                      </button>
                                    ))}
                                  </div>
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {matrix.groups.length > 40 ? (
                      <p className="mt-2 text-xs text-muted">
                        Showing first 40 groups of {matrix.groups.length}.
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </Card>
            ),
          },
          {
            value: "groups",
            label: "Groups",
            content: (
              <Card className="p-5">
                <h2 className="text-lg font-semibold text-ink">Security groups</h2>
                <ul className="mt-3 space-y-1 text-sm">
                  {groups.map((g) => (
                    <li
                      key={g.id}
                      className="border-l-2 border-border-subtle pl-3 text-ink"
                      style={{ marginLeft: g.full_name?.includes("/") ? 12 : 0 }}
                    >
                      <span className="font-mono text-accent">{g.name}</span>
                      {g.full_name ? (
                        <span className="ml-2 text-muted">{g.full_name}</span>
                      ) : null}
                    </li>
                  ))}
                  {groups.length === 0 ? (
                    <li className="text-muted">No groups loaded — open Matrix or load a model.</li>
                  ) : null}
                </ul>
              </Card>
            ),
          },
          {
            value: "model",
            label: "Model ACL",
            content: (
              <div className="space-y-6">
                <form onSubmit={onLoadModel} className="flex flex-wrap items-end gap-3">
                  <Input
                    label="Model"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    className="w-64 font-mono"
                  />
                  <Button type="submit" variant="secondary" disabled={busy} loading={busy}>
                    Load
                  </Button>
                </form>
                {error ? <ErrorNotice message={error} /> : null}
                {notice ? (
                  <Callout variant="info" title="Notice">
                    {notice}
                  </Callout>
                ) : null}
                <div className="grid gap-8 lg:grid-cols-2">
                  <Card className="space-y-4 p-6">
                    <form onSubmit={onCreateAccess} className="space-y-4">
                      <h2 className="text-xl font-semibold text-ink">New access right</h2>
                      {!accessForm.group_id ? (
                        <Callout variant="warning" title="Global access line">
                          Empty group applies to all users — use only when you understand compendium §6.
                        </Callout>
                      ) : null}
                      <Input
                        label="Name"
                        required
                        value={accessForm.name}
                        onChange={(e) =>
                          setAccessForm({ ...accessForm, name: e.target.value })
                        }
                        placeholder={`${model} user`}
                      />
                      <Select
                        label="Group (empty = all users)"
                        options={[
                          { value: "", label: "— all / no group —" },
                          ...groups.map((g) => ({
                            value: String(g.id),
                            label: g.full_name || g.name,
                          })),
                        ]}
                        value={accessForm.group_id}
                        onChange={(e) =>
                          setAccessForm({ ...accessForm, group_id: e.target.value })
                        }
                      />
                      <div className="flex flex-wrap gap-4 text-sm">
                        {(
                          [
                            ["perm_read", "Read"],
                            ["perm_write", "Write"],
                            ["perm_create", "Create"],
                            ["perm_unlink", "Delete"],
                          ] as const
                        ).map(([key, label]) => (
                          <label key={key} className="flex items-center gap-2 text-ink">
                            <input
                              type="checkbox"
                              checked={accessForm[key]}
                              onChange={(e) =>
                                setAccessForm({ ...accessForm, [key]: e.target.checked })
                              }
                            />
                            {label}
                          </label>
                        ))}
                      </div>
                      <Button
                        type="submit"
                        variant="primary"
                        disabled={busy || !canMutate}
                        title={mutateBlocked ?? undefined}
                        loading={busy}
                      >
                        Create access
                      </Button>
                    </form>
                  </Card>

                  <Card className="space-y-4 p-6">
                    <form onSubmit={onCreateRule} className="space-y-4">
                      <h2 className="text-xl font-semibold text-ink">New record rule</h2>
                      {!ruleForm.group_id ? (
                        <Callout variant="danger" title="Global record rule">
                          Empty group creates a global rule — compendium §6 warns this affects all users.
                        </Callout>
                      ) : null}
                      <Input
                        label="Name"
                        required
                        value={ruleForm.name}
                        onChange={(e) => setRuleForm({ ...ruleForm, name: e.target.value })}
                      />
                      <DomainBuilder
                        label="Domain"
                        value={ruleForm.domain_force}
                        onChange={(domain_force) =>
                          setRuleForm({ ...ruleForm, domain_force })
                        }
                      />
                      <Select
                        label="Group (optional)"
                        options={[
                          { value: "", label: "— global —" },
                          ...groups.map((g) => ({
                            value: String(g.id),
                            label: g.full_name || g.name,
                          })),
                        ]}
                        value={ruleForm.group_id}
                        onChange={(e) =>
                          setRuleForm({ ...ruleForm, group_id: e.target.value })
                        }
                      />
                      <div className="flex flex-wrap gap-4 text-sm">
                        {(
                          [
                            ["perm_read", "Read"],
                            ["perm_write", "Write"],
                            ["perm_create", "Create"],
                            ["perm_unlink", "Delete"],
                          ] as const
                        ).map(([key, label]) => (
                          <label key={key} className="flex items-center gap-2 text-ink">
                            <input
                              type="checkbox"
                              checked={ruleForm[key]}
                              onChange={(e) =>
                                setRuleForm({ ...ruleForm, [key]: e.target.checked })
                              }
                            />
                            {label}
                          </label>
                        ))}
                      </div>
                      <Button
                        type="submit"
                        variant="primary"
                        disabled={busy || !canMutate}
                        title={mutateBlocked ?? undefined}
                        loading={busy}
                      >
                        Create rule
                      </Button>
                    </form>
                  </Card>
                </div>

                <div className="space-y-6">
                  <div>
                    <h2 className="text-xl font-semibold text-ink">Access on {model}</h2>
                    <div className="mt-4">
                      <DataTable
                        columns={rightsColumns}
                        rows={rights}
                        rowKey={(r) => String(r.id)}
                        emptyState={
                          <p className="text-sm text-muted">
                            No access rows for this model (or load first).
                          </p>
                        }
                      />
                    </div>
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-ink">Record rules</h2>
                    <ul className="mt-4 space-y-3">
                      {rules.map((r) => (
                        <li
                          key={r.id}
                          className="rounded-md border border-border-subtle p-4 text-sm"
                        >
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <p className="font-medium text-ink">
                                {r.name}{" "}
                                <span className="text-muted">
                                  · #{r.id}
                                  {r.global ? " · global" : ""}
                                </span>
                              </p>
                              <pre className="mt-2 overflow-auto rounded-md bg-surface-muted p-2 font-mono text-xs text-muted">
                                {r.domain_force ?? "(empty)"}
                              </pre>
                            </div>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              disabled={busy || !canAdvanced}
                              title={advancedBlocked ?? undefined}
                              onClick={() =>
                                setPendingDelete({
                                  kind: "rule",
                                  id: r.id,
                                  name: r.name,
                                  risks: [
                                    "May expose records previously filtered by domain",
                                    "Or hide records if other rules still apply",
                                    "Snapshot allows restoring the rule definition when possible",
                                  ],
                                })
                              }
                            >
                              Delete
                            </Button>
                          </div>
                        </li>
                      ))}
                      {rules.length === 0 ? (
                        <li className="text-sm text-muted">No record rules for this model.</li>
                      ) : null}
                    </ul>
                  </div>
                </div>

                <Card className="p-5">
                  <h2 className="text-xl font-semibold text-ink">
                    {mcGuidance?.title ?? "Multi-company pack"}
                  </h2>
                  <p className="mt-2 text-sm text-muted">
                    {mcGuidance?.body ??
                      "Adds x_company_id + global record rule with company_ids domain on custom models."}
                  </p>
                  <Button
                    type="button"
                    variant="secondary"
                    className="mt-3"
                    disabled={busy || !model.startsWith("x_")}
                    onClick={async () => {
                      setBusy(true);
                      setError(null);
                      try {
                        const res = await api.applyMultiCompanyLive(connectionId, [model]);
                        setNotice(
                          `Multi-company: ${res.fields_created} field(s), ${res.rules_created} rule(s)` +
                            (res.warnings.length ? ` · ${res.warnings.join("; ")}` : ""),
                        );
                        await refresh(model);
                      } catch (err) {
                        setError(
                          err instanceof Error ? err.message : "Multi-company apply failed",
                        );
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    Apply live pack to loaded model
                  </Button>
                </Card>

                <Card className="p-5">
                  <h2 className="text-xl font-semibold text-ink">Documents folder map</h2>
                  <p className="mt-1 text-xs text-muted">
                    {docsGate?.available
                      ? "Map custom models to a Documents folder (Enterprise documents module)."
                      : docsGate?.message ??
                        "Documents module not available — config is stored but attach automation is suggestion-only."}
                  </p>
                  <div className="mt-3 flex flex-wrap items-end gap-2">
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={busy || !docsGate?.available}
                      onClick={async () => {
                        setBusy(true);
                        try {
                          setDocsFolders(await api.listDocumentsFolders(connectionId));
                          setNotice("Loaded Documents folders");
                        } catch (err) {
                          setError(err instanceof Error ? err.message : "Folder list failed");
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      Load folders
                    </Button>
                    <Select
                      options={[
                        { value: "", label: "Select folder" },
                        ...docsFolders.map((f) => ({
                          value: String(f.id),
                          label: f.name ?? `#${f.id}`,
                        })),
                      ]}
                      value={docsFolderId}
                      onChange={(e) => setDocsFolderId(e.target.value)}
                      disabled={docsFolders.length === 0}
                    />
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={busy || !model.startsWith("x_") || !docsFolderId}
                      onClick={async () => {
                        setBusy(true);
                        try {
                          const res = await api.setDocumentsFolder(connectionId, {
                            model,
                            folder_id: Number(docsFolderId),
                          });
                          setDocsMapping(res.mapping);
                          setNotice(`Mapped ${model} → folder ${docsFolderId}`);
                        } catch (err) {
                          setError(err instanceof Error ? err.message : "Save folder map failed");
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      Save for loaded model
                    </Button>
                  </div>
                  {Object.keys(docsMapping).length > 0 ? (
                    <ul className="mt-3 space-y-1 font-mono text-xs text-muted">
                      {Object.entries(docsMapping).map(([m, fid]) => (
                        <li key={m}>
                          {m} → folder {fid}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </Card>
              </div>
            ),
          },
        ]}
      />

      <ConfirmDialogV2
        open={pendingDelete != null}
        riskLevel="danger"
        title="Delete access metadata?"
        warning={
          pendingDelete
            ? `Delete ${pendingDelete.kind === "access" ? "access right" : "record rule"} “${pendingDelete.name}”?`
            : ""
        }
        risks={pendingDelete?.risks ?? []}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => proceedDelete()}
      />
    </div>
  );
}
