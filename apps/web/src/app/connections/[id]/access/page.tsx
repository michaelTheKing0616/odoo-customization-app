"use client";

import Link from "next/link";
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
  const [confirmTyped, setConfirmTyped] = useState("");
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
    if (!pendingDelete || confirmTyped !== CONFIRM_PHRASE) return;
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
      setConfirmTyped("");
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

  return (
    <main className="min-h-screen bg-[radial-gradient(ellipse_at_top,_#3d2a38_0%,_#1a1218_50%,_#0c090b_100%)] px-6 py-10 text-[#f4eef2]">
      <div className="mx-auto max-w-5xl">
        <div className="flex flex-wrap gap-4 text-sm">
          <Link href={`/connections/${connectionId}`} className="text-[#c9a9c0] hover:underline">
            ← Metadata
          </Link>
          <Link
            href={`/connections/${connectionId}/builder`}
            className="text-[#8f7a88] hover:underline"
          >
            Builder
          </Link>
          <Link
            href={`/connections/${connectionId}/automations`}
            className="text-[#8f7a88] hover:underline"
          >
            Automations
          </Link>
        </div>
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl text-[#faf6f9]">
          Access rights
        </h1>
        <p className="mt-1 text-sm text-[#8f7a88]">
          {connection?.name ?? connectionId} ·{" "}
          <code className="text-[#c9a9c0]">ir.model.access</code> + simple{" "}
          <code className="text-[#c9a9c0]">ir.rule</code> · matrix below
        </p>
        <VersionAwarenessBanner capabilities={connection?.capabilities} />
        {mutateBlocked && (
          <p className="mt-2 text-sm text-[#e8d09f]">{mutateBlocked}</p>
        )}
        {!mutateBlocked && advancedBlocked && (
          <p className="mt-2 text-sm text-[#e8d09f]">{advancedBlocked}</p>
        )}

        <section className="mt-8 border border-[#3d2a38] bg-[#0f1a16]/70 p-5">
          <h2 className="font-[family-name:var(--font-display)] text-xl">
            Access matrix
          </h2>
          <p className="mt-1 text-xs text-[#8f7a88]">
            Groups × models. Click R/W/C/D to toggle. Empty cell creates a new access line.
          </p>
          <div className="mt-3 flex flex-wrap items-end gap-3">
            <label className="text-sm">
              <span className="text-[#a8909e]">Models (comma-separated)</span>
              <input
                value={matrixModels}
                onChange={(e) => setMatrixModels(e.target.value)}
                className="mt-1 block w-[28rem] max-w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
              />
            </label>
            <button
              type="button"
              disabled={matrixBusy}
              onClick={() => void loadMatrix()}
              className="h-10 border border-[#c9a9c0] px-4 text-sm text-[#c9a9c0] disabled:opacity-60"
            >
              Load matrix
            </button>
          </div>
          {matrix && (
            <div className="mt-4 overflow-auto">
              <table className="min-w-full text-left text-xs">
                <thead className="text-[#8f7a88]">
                  <tr>
                    <th className="sticky left-0 bg-[#0f1a16] py-2 pr-3">Group \\ Model</th>
                    {matrix.models.map((m) => (
                      <th key={m} className="px-2 py-2 font-mono">
                        {m}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {matrix.groups.slice(0, 40).map((g) => (
                    <tr key={g.id} className="border-t border-[#1e2f29]">
                      <td className="sticky left-0 bg-[#0f1a16] py-2 pr-3 text-[#c9a9c0]">
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
                                    mutateBlocked ??
                                    `${label} ${cell[key] ? "on" : "off"}`
                                  }
                                  onClick={() => void toggleMatrixPerm(cell, g.id, key)}
                                  className={`px-1 ${
                                    cell[key]
                                      ? "bg-[#714B67] text-white"
                                      : "border border-[#3d2a38] text-[#8f7a88]"
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
              {matrix.groups.length > 40 && (
                <p className="mt-2 text-xs text-[#8f7a88]">
                  Showing first 40 groups of {matrix.groups.length}.
                </p>
              )}
            </div>
          )}
        </section>

        <form onSubmit={onLoadModel} className="mt-6 flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="text-[#a8909e]">Model</span>
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="mt-1 block w-64 border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="h-10 border border-[#c9a9c0] px-4 text-sm text-[#c9a9c0] disabled:opacity-60"
          >
            Load
          </button>
        </form>

        {error && <p className="mt-4 text-sm text-[#f0a8a0]">{error}</p>}
        {notice && <p className="mt-4 text-sm text-[#c9a9c0]">{notice}</p>}

        {pendingDelete && (
          <div className="mt-6 border border-[#a85b4a] bg-[#2a1512] p-5">
            <h2 className="font-[family-name:var(--font-display)] text-xl text-[#f0a8a0]">
              Warning
            </h2>
            <p className="mt-2 text-sm text-[#e8cfc9]">
              Delete {pendingDelete.kind === "access" ? "access right" : "record rule"}{" "}
              <strong>{pendingDelete.name}</strong>? This changes who can see or edit
              records.
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
            onSubmit={onCreateAccess}
            className="space-y-4 border border-[#3d2a38] bg-[#0f1a16]/70 p-6"
          >
            <h2 className="font-[family-name:var(--font-display)] text-xl">New access right</h2>
            <label className="block text-sm">
              <span className="text-[#a8909e]">Name</span>
              <input
                required
                value={accessForm.name}
                onChange={(e) => setAccessForm({ ...accessForm, name: e.target.value })}
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
                placeholder={`${model} user`}
              />
            </label>
            <label className="block text-sm">
              <span className="text-[#a8909e]">Group (empty = all users)</span>
              <select
                value={accessForm.group_id}
                onChange={(e) => setAccessForm({ ...accessForm, group_id: e.target.value })}
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
              >
                <option value="">— all / no group —</option>
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.full_name || g.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex flex-wrap gap-4 text-sm">
              {(
                [
                  ["perm_read", "Read"],
                  ["perm_write", "Write"],
                  ["perm_create", "Create"],
                  ["perm_unlink", "Delete"],
                ] as const
              ).map(([key, label]) => (
                <label key={key} className="flex items-center gap-2">
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
            <button
              type="submit"
              disabled={busy || !canMutate}
              title={mutateBlocked ?? undefined}
              className="h-11 bg-[#714B67] px-5 text-sm font-semibold text-white disabled:opacity-60"
            >
              Create access
            </button>
          </form>

          <form
            onSubmit={onCreateRule}
            className="space-y-4 border border-[#3d2a38] bg-[#0f1a16]/70 p-6"
          >
            <h2 className="font-[family-name:var(--font-display)] text-xl">New record rule</h2>
            <p className="text-sm text-[#8f7a88]">
              Empty group = global rule. Domain must be a list string.
            </p>
            <label className="block text-sm">
              <span className="text-[#a8909e]">Name</span>
              <input
                required
                value={ruleForm.name}
                onChange={(e) => setRuleForm({ ...ruleForm, name: e.target.value })}
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
              />
            </label>
            <div className="block text-sm">
              <DomainBuilder
                label="Domain"
                value={ruleForm.domain_force}
                onChange={(domain_force) =>
                  setRuleForm({ ...ruleForm, domain_force })
                }
              />
            </div>
            <label className="block text-sm">
              <span className="text-[#a8909e]">Group (optional)</span>
              <select
                value={ruleForm.group_id}
                onChange={(e) => setRuleForm({ ...ruleForm, group_id: e.target.value })}
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
              >
                <option value="">— global —</option>
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.full_name || g.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex flex-wrap gap-4 text-sm">
              {(
                [
                  ["perm_read", "Read"],
                  ["perm_write", "Write"],
                  ["perm_create", "Create"],
                  ["perm_unlink", "Delete"],
                ] as const
              ).map(([key, label]) => (
                <label key={key} className="flex items-center gap-2">
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
            <button
              type="submit"
              disabled={busy || !canMutate}
              title={mutateBlocked ?? undefined}
              className="h-11 bg-[#714B67] px-5 text-sm font-semibold text-white disabled:opacity-60"
            >
              Create rule
            </button>
          </form>
        </div>

        <section className="mt-10">
          <h2 className="font-[family-name:var(--font-display)] text-xl">Access on {model}</h2>
          <table className="mt-4 w-full text-left text-sm">
            <thead className="text-[#8f7a88]">
              <tr>
                <th className="py-2 pr-3">Name</th>
                <th className="py-2 pr-3">Group</th>
                <th className="py-2 pr-3">CRUD</th>
                <th className="py-2"> </th>
              </tr>
            </thead>
            <tbody>
              {rights.map((r) => (
                <tr key={r.id} className="border-t border-[#1e2f29]">
                  <td className="py-2 pr-3">{r.name}</td>
                  <td className="py-2 pr-3 text-[#c9a9c0]">
                    {r.group_name ?? "(all)"}
                  </td>
                  <td className="py-2 pr-3 font-mono text-xs text-[#8f7a88]">
                    {[r.perm_read && "R", r.perm_write && "W", r.perm_create && "C", r.perm_unlink && "D"]
                      .filter(Boolean)
                      .join("") || "—"}
                  </td>
                  <td className="py-2">
                    <button
                      type="button"
                      disabled={busy || !canAdvanced}
                      title={advancedBlocked ?? undefined}
                      className="text-xs text-[#f0a8a0] hover:underline disabled:opacity-50"
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
                    </button>
                  </td>
                </tr>
              ))}
              {rights.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-3 text-[#8f7a88]">
                    No access rows for this model (or load first).
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>

        <section className="mt-10">
          <h2 className="font-[family-name:var(--font-display)] text-xl">Record rules</h2>
          <ul className="mt-4 space-y-3">
            {rules.map((r) => (
              <li key={r.id} className="border border-[#3d2a38] p-4 text-sm">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-medium">
                      {r.name}{" "}
                      <span className="text-[#8f7a88]">
                        · #{r.id}
                        {r.global ? " · global" : ""}
                      </span>
                    </p>
                    <pre className="mt-2 overflow-auto bg-[#0c090b] p-2 text-xs text-[#d4c4ce]">
                      {r.domain_force ?? "(empty)"}
                    </pre>
                  </div>
                  <button
                    type="button"
                    disabled={busy || !canAdvanced}
                    title={advancedBlocked ?? undefined}
                    className="text-xs text-[#f0a8a0] hover:underline disabled:opacity-50"
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
                  </button>
                </div>
              </li>
            ))}
            {rules.length === 0 && (
              <li className="text-sm text-[#8f7a88]">No record rules for this model.</li>
            )}
          </ul>
        </section>

        <section className="mt-8 border border-[#3d2a38] bg-[#0f1a16]/70 p-5">
          <h2 className="font-[family-name:var(--font-display)] text-xl text-[#faf6f9]">
            {mcGuidance?.title ?? "Multi-company pack"}
          </h2>
          <p className="mt-2 text-sm text-[#a8909e]">
            {mcGuidance?.body ??
              "Adds x_company_id + global record rule with company_ids domain on custom models."}
          </p>
          <button
            type="button"
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
                setError(err instanceof Error ? err.message : "Multi-company apply failed");
              } finally {
                setBusy(false);
              }
            }}
            className="mt-3 border border-[#c9a9c0] px-3 py-1 text-sm text-[#c9a9c0]"
          >
            Apply live pack to loaded model
          </button>
        </section>

        <section className="mt-8 border border-[#3d2a38] bg-[#0f1a16]/70 p-5">
          <h2 className="font-[family-name:var(--font-display)] text-xl text-[#faf6f9]">
            Documents folder map
          </h2>
          <p className="mt-1 text-xs text-[#8f7a88]">
            {docsGate?.available
              ? "Map custom models to a Documents folder (Enterprise documents module)."
              : docsGate?.message ??
                "Documents module not available — config is stored but attach automation is suggestion-only."}
          </p>
          <div className="mt-3 flex flex-wrap items-end gap-2">
            <button
              type="button"
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
              className="border border-[#c9a9c0] px-3 py-1 text-sm text-[#c9a9c0]"
            >
              Load folders
            </button>
            <select
              value={docsFolderId}
              onChange={(e) => setDocsFolderId(e.target.value)}
              className="border border-[#3d2a38] bg-[#0c090b] px-2 py-1 text-sm"
              disabled={docsFolders.length === 0}
            >
              <option value="">Select folder</option>
              {docsFolders.map((f) => (
                <option key={f.id} value={String(f.id)}>
                  {f.name ?? `#${f.id}`}
                </option>
              ))}
            </select>
            <button
              type="button"
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
              className="border border-[#c9a9c0] px-3 py-1 text-sm text-[#c9a9c0]"
            >
              Save for loaded model
            </button>
          </div>
          {Object.keys(docsMapping).length > 0 && (
            <ul className="mt-3 space-y-1 font-mono text-xs text-[#8f7a88]">
              {Object.entries(docsMapping).map(([m, fid]) => (
                <li key={m}>
                  {m} → folder {fid}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
