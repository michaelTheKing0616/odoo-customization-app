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
  SnapshotRow,
} from "@/lib/api";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { CapabilityProbePanel } from "@/components/CapabilityProbePanel";
import { ExplainThisButton } from "@/components/expert/ExplainThisButton";
import {
  advancedMutationAllowed,
  advancedMutationBlockedReason,
  mutationAllowed,
  mutationBlockedReason,
} from "@/lib/capabilities";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { PageHeader } from "@/components/ui/layout-primitives";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Disclosure } from "@/components/ui/Disclosure";
import { reportApiError } from "@/lib/api-error";
import { useSyncShellContext } from "@/lib/use-sync-shell-context";
import {
  ACCESS_DELETE_RISKS,
  CONFIRM_PHRASE,
  DEFAULT_ACCESS_MODEL,
  RULE_DELETE_RISKS,
  composerSessionState,
  defaultAccessForm,
  defaultRuleForm,
  designerHref,
  isComposerDirty,
  parseModelList,
  type AccessComposerForm,
  type AccessPane,
  type RuleComposerForm,
} from "@/lib/accessForm";
import { AccessComposer } from "@/components/access/AccessComposer";
import { AccessDetail } from "@/components/access/AccessDetail";
import { AccessExtras } from "@/components/access/AccessExtras";
import { AccessMatrixPanel } from "@/components/access/AccessMatrixPanel";
import { AccessModelPicker } from "@/components/access/AccessModelPicker";
import { AccessRightsList } from "@/components/access/AccessRightsList";
import { AccessSessionBar } from "@/components/access/AccessSessionBar";
import { AccessSnapshots } from "@/components/access/AccessSnapshots";
import { RecordRuleComposer } from "@/components/access/RecordRuleComposer";
import { RecordRuleDetail } from "@/components/access/RecordRuleDetail";
import { RecordRulesList } from "@/components/access/RecordRulesList";

type PendingDelete =
  | { kind: "access"; id: number; name: string }
  | { kind: "rule"; id: number; name: string };

export default function AccessPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [probing, setProbing] = useState(false);
  const [model, setModel] = useState(DEFAULT_ACCESS_MODEL);
  const [groups, setGroups] = useState<GroupRow[]>([]);
  const [rights, setRights] = useState<AccessRightRow[]>([]);
  const [rules, setRules] = useState<RecordRuleRow[]>([]);
  const [snapshots, setSnapshots] = useState<SnapshotRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [listLoading, setListLoading] = useState(true);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null);
  const [pane, setPane] = useState<AccessPane>("new-access");
  const [selectedAccessId, setSelectedAccessId] = useState<number | null>(null);
  const [selectedRuleId, setSelectedRuleId] = useState<number | null>(null);
  const [rightsQuery, setRightsQuery] = useState("");
  const [rulesQuery, setRulesQuery] = useState("");
  const [savedOnce, setSavedOnce] = useState(false);

  const [matrixModels, setMatrixModels] = useState(DEFAULT_ACCESS_MODEL);
  const [matrix, setMatrix] = useState<AccessMatrixOut | null>(null);
  const [matrixBusy, setMatrixBusy] = useState(false);
  const [mcGuidance, setMcGuidance] = useState<{ title: string; body: string } | null>(null);
  const [docsGate, setDocsGate] = useState<{
    available: boolean;
    message?: string | null;
  } | null>(null);
  const [docsFolders, setDocsFolders] = useState<Array<{ id: number; name: string | null }>>([]);
  const [docsFolderId, setDocsFolderId] = useState("");
  const [docsMapping, setDocsMapping] = useState<Record<string, number>>({});

  const [accessForm, setAccessForm] = useState<AccessComposerForm>(() => defaultAccessForm());
  const [accessBaseline, setAccessBaseline] = useState<AccessComposerForm>(() =>
    defaultAccessForm(),
  );
  const [ruleForm, setRuleForm] = useState<RuleComposerForm>(() => defaultRuleForm());
  const [ruleBaseline, setRuleBaseline] = useState<RuleComposerForm>(() => defaultRuleForm());

  useSyncShellContext({ model });

  const patchAccess = useCallback((next: Partial<AccessComposerForm>) => {
    setAccessForm((f) => ({ ...f, ...next }));
  }, []);
  const patchRule = useCallback((next: Partial<RuleComposerForm>) => {
    setRuleForm((f) => ({ ...f, ...next }));
  }, []);

  const refresh = useCallback(
    async (target: string) => {
      const [conn, gs, rs, rls, snaps] = await Promise.all([
        api.getConnection(connectionId),
        api.listGroups(connectionId),
        api.listAccessRights(connectionId, target),
        api.listRecordRules(connectionId, target),
        api.listSnapshots(connectionId).catch(() => [] as SnapshotRow[]),
      ]);
      setConnection(conn);
      setGroups(gs);
      setRights(rs);
      setRules(rls);
      setSnapshots(snaps);
    },
    [connectionId],
  );

  useEffect(() => {
    setListLoading(true);
    refresh(DEFAULT_ACCESS_MODEL)
      .catch((err: Error) => setError(err.message))
      .finally(() => setListLoading(false));
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

  useEffect(() => {
    if (typeof window === "undefined") return;
    const fromQuery = new URLSearchParams(window.location.search).get("model");
    if (!fromQuery) return;
    setModel(fromQuery);
    setMatrixModels(fromQuery);
    setListLoading(true);
    refresh(fromQuery)
      .catch((err: Error) => setError(err.message))
      .finally(() => setListLoading(false));
  }, [refresh]);

  async function onLoadModel(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await refresh(model);
      setNotice(`Loaded access for ${model}`);
      setSelectedAccessId(null);
      setSelectedRuleId(null);
      setPane("new-access");
    } catch (err) {
      reportApiError(err, setError, { fallback: "Load failed", toast: true });
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
      setSavedOnce(true);
      const next = { ...accessForm, name: "" };
      setAccessForm(next);
      setAccessBaseline(next);
      await refresh(model);
      setSelectedAccessId(created.id);
      setSelectedRuleId(null);
      setPane("access");
    } catch (err) {
      reportApiError(err, setError, { fallback: "Create access failed", toast: true });
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
        group_ids: ruleForm.group_ids,
        perm_read: ruleForm.perm_read,
        perm_write: ruleForm.perm_write,
        perm_create: ruleForm.perm_create,
        perm_unlink: ruleForm.perm_unlink,
      });
      setNotice(`Created record rule #${created.id}`);
      setSavedOnce(true);
      const next = { ...ruleForm, name: "" };
      setRuleForm(next);
      setRuleBaseline(next);
      await refresh(model);
      setSelectedRuleId(created.id);
      setSelectedAccessId(null);
      setPane("rule");
    } catch (err) {
      reportApiError(err, setError, { fallback: "Create rule failed", toast: true });
    } finally {
      setBusy(false);
    }
  }

  async function loadMatrix() {
    setMatrixBusy(true);
    setError(null);
    try {
      const data = await api.accessMatrix(connectionId, parseModelList(matrixModels));
      setMatrix(data);
      setNotice(`Matrix loaded for ${data.models.length} model(s)`);
    } catch (err) {
      reportApiError(err, setError, { fallback: "Matrix load failed", toast: true });
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
      await refresh(model);
    } catch (err) {
      reportApiError(err, setError, { fallback: "Update failed", toast: true });
      setMatrixBusy(false);
    }
  }

  function cellFor(
    modelName: string,
    groupId: number | null,
  ): AccessMatrixOut["cells"][number] {
    const found = matrix?.cells.find(
      (c) =>
        c.model === modelName && (c.group_id ?? null) === groupId && c.active !== false,
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

  async function onRollback(snapshotId: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await api.rollbackSnapshot(connectionId, snapshotId);
      setNotice(`Restored ${res.restored} #${res.id}`);
      await refresh(model);
    } catch (err) {
      reportApiError(err, setError, { fallback: "Rollback failed", toast: true });
    } finally {
      setBusy(false);
    }
  }

  const canMutate = mutationAllowed(connection);
  const mutateBlocked = mutationBlockedReason(connection);
  const canAdvanced = advancedMutationAllowed(connection);
  const advancedBlocked = advancedMutationBlockedReason(connection);

  const selectedAccess = rights.find((r) => r.id === selectedAccessId) ?? null;
  const selectedRule = rules.find((r) => r.id === selectedRuleId) ?? null;
  const accessDirty = isComposerDirty(accessForm, accessBaseline);
  const ruleDirty = isComposerDirty(ruleForm, ruleBaseline);
  const composingAccess = pane === "new-access";
  const composingRule = pane === "new-rule";
  const sessionState = composerSessionState({
    dirty: composingAccess ? accessDirty : composingRule ? ruleDirty : false,
    savedOnce,
  });

  return (
    <div className="mx-auto max-w-6xl" data-testid="access-page">
      <PageHeader
        title="Access"
        description={`${connection?.name ?? connectionId} · Access rights, group grants, and record-rule domains.`}
        actions={
          <>
            <Button variant="secondary" size="sm" asChild>
              <Link href={designerHref(connectionId, model)} data-testid="access-designer-link">
                Open in View Designer
              </Link>
            </Button>
            <ExplainThisButton
              question={`Explain access rights and record rules for model ${model}`}
              label="Explain access"
            />
          </>
        }
      />
      <p className="mt-2 text-sm text-muted">
        Access lines grant CRUD. Record rules filter which rows a group can see or change. Global
        grants (no group) affect every user — confirm before you delete.
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

      {error ? (
        <ErrorNotice message={error} className="mt-4" onRetry={() => void refresh(model)} />
      ) : null}
      {notice ? (
        <Callout variant="info" title="Notice" className="mt-4">
          {notice}
        </Callout>
      ) : null}

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(240px,320px)_minmax(0,1fr)]">
        <div className="space-y-6">
          <AccessModelPicker
            model={model}
            onModelChange={setModel}
            onLoad={onLoadModel}
            busy={busy}
          />
          <AccessRightsList
            rows={rights}
            loading={listLoading}
            selectedId={selectedAccessId}
            query={rightsQuery}
            onQueryChange={setRightsQuery}
            onSelect={(row) => {
              setSelectedAccessId(row.id);
              setSelectedRuleId(null);
              setPane("access");
              setNotice(null);
            }}
            onCreate={() => {
              setSelectedAccessId(null);
              setSelectedRuleId(null);
              setPane("new-access");
              setNotice(null);
            }}
          />
          <RecordRulesList
            rows={rules}
            loading={listLoading}
            selectedId={selectedRuleId}
            query={rulesQuery}
            onQueryChange={setRulesQuery}
            onSelect={(row) => {
              setSelectedRuleId(row.id);
              setSelectedAccessId(null);
              setPane("rule");
              setNotice(null);
            }}
            onCreate={() => {
              setSelectedRuleId(null);
              setSelectedAccessId(null);
              setPane("new-rule");
              setNotice(null);
            }}
          />
          <AccessSnapshots
            connectionId={connectionId}
            snapshots={snapshots}
            busy={busy}
            onRollback={onRollback}
          />
        </div>

        <div className="space-y-4">
          {pane === "access" && selectedAccess ? (
            <AccessDetail
              key={selectedAccess.id}
              connectionId={connectionId}
              row={selectedAccess}
              groups={groups}
              busy={busy}
              canMutate={canMutate}
              canDelete={canAdvanced}
              mutateBlocked={mutateBlocked}
              deleteBlocked={advancedBlocked}
              onSave={async (patch) => {
                setBusy(true);
                setError(null);
                try {
                  await api.updateAccessRight(connectionId, selectedAccess.id, patch);
                  setNotice(`Updated access #${selectedAccess.id}`);
                  await refresh(model);
                } catch (err) {
                  reportApiError(err, setError, { fallback: "Update failed", toast: true });
                } finally {
                  setBusy(false);
                }
              }}
              onDelete={() =>
                setPendingDelete({
                  kind: "access",
                  id: selectedAccess.id,
                  name: selectedAccess.name,
                })
              }
            />
          ) : pane === "rule" && selectedRule ? (
            <RecordRuleDetail
              key={selectedRule.id}
              connectionId={connectionId}
              row={selectedRule}
              groups={groups}
              busy={busy}
              canMutate={canMutate}
              canDelete={canAdvanced}
              mutateBlocked={mutateBlocked}
              deleteBlocked={advancedBlocked}
              onSave={async (patch) => {
                setBusy(true);
                setError(null);
                try {
                  await api.updateRecordRule(connectionId, selectedRule.id, patch);
                  setNotice(`Updated rule #${selectedRule.id}`);
                  await refresh(model);
                } catch (err) {
                  reportApiError(err, setError, { fallback: "Update failed", toast: true });
                } finally {
                  setBusy(false);
                }
              }}
              onDelete={() =>
                setPendingDelete({
                  kind: "rule",
                  id: selectedRule.id,
                  name: selectedRule.name,
                })
              }
            />
          ) : composingRule ? (
            <>
              <AccessSessionBar
                sessionState={sessionState}
                busy={busy}
                canDiscard={ruleDirty}
                submitLabel="Create rule"
                onDiscard={() => {
                  setRuleForm(ruleBaseline);
                  setSelectedRuleId(null);
                }}
              />
              <RecordRuleComposer
                model={model}
                form={ruleForm}
                groups={groups}
                onChange={patchRule}
                onSubmit={onCreateRule}
                busy={busy}
                canSubmit={canMutate}
                submitBlockedReason={mutateBlocked}
              />
            </>
          ) : (
            <>
              <AccessSessionBar
                sessionState={sessionState}
                busy={busy}
                canDiscard={accessDirty}
                submitLabel="Create access"
                onDiscard={() => {
                  setAccessForm(accessBaseline);
                  setSelectedAccessId(null);
                }}
              />
              <AccessComposer
                model={model}
                form={accessForm}
                groups={groups}
                onChange={patchAccess}
                onSubmit={onCreateAccess}
                busy={busy}
                canSubmit={canMutate}
                submitBlockedReason={mutateBlocked}
              />
            </>
          )}
        </div>
      </div>

      <Disclosure title="Access matrix" className="mt-8" testId="access-matrix-disclosure">
        <AccessMatrixPanel
          modelsInput={matrixModels}
          onModelsInput={setMatrixModels}
          matrix={matrix}
          busy={matrixBusy}
          canMutate={canMutate}
          mutateBlocked={mutateBlocked}
          onLoad={() => void loadMatrix()}
          onToggle={toggleMatrixPerm}
          cellFor={cellFor}
        />
      </Disclosure>

      <Disclosure title="Groups, multi-company, Documents" className="mt-4">
        <AccessExtras
          model={model}
          busy={busy}
          groups={groups}
          mcGuidance={mcGuidance}
          docsGate={docsGate}
          docsFolders={docsFolders}
          docsFolderId={docsFolderId}
          docsMapping={docsMapping}
          onDocsFolderId={setDocsFolderId}
          onApplyMultiCompany={async () => {
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
              reportApiError(err, setError, {
                fallback: "Multi-company apply failed",
                toast: true,
              });
            } finally {
              setBusy(false);
            }
          }}
          onLoadFolders={async () => {
            setBusy(true);
            try {
              setDocsFolders(await api.listDocumentsFolders(connectionId));
              setNotice("Loaded Documents folders");
            } catch (err) {
              reportApiError(err, setError, { fallback: "Folder list failed", toast: true });
            } finally {
              setBusy(false);
            }
          }}
          onSaveFolder={async () => {
            setBusy(true);
            try {
              const res = await api.setDocumentsFolder(connectionId, {
                model,
                folder_id: Number(docsFolderId),
              });
              setDocsMapping(res.mapping);
              setNotice(`Mapped ${model} → folder ${docsFolderId}`);
            } catch (err) {
              reportApiError(err, setError, { fallback: "Save folder map failed", toast: true });
            } finally {
              setBusy(false);
            }
          }}
        />
      </Disclosure>

      <ConfirmDialogV2
        open={pendingDelete != null}
        riskLevel="danger"
        title="Delete access metadata"
        warning={
          pendingDelete
            ? `Delete ${pendingDelete.kind === "access" ? "access right" : "record rule"} “${pendingDelete.name}”?`
            : ""
        }
        risks={pendingDelete?.kind === "rule" ? RULE_DELETE_RISKS : ACCESS_DELETE_RISKS}
        phrase={CONFIRM_PHRASE}
        snapshotNote="A snapshot is taken so the definition can be restored when Odoo allows it."
        busy={busy}
        onCancel={() => setPendingDelete(null)}
        onConfirm={async (phrase) => {
          if (!pendingDelete) return;
          setBusy(true);
          setError(null);
          setNotice(null);
          try {
            if (pendingDelete.kind === "access") {
              const res = await api.deleteAccessRight(connectionId, pendingDelete.id, {
                confirm_advanced: true,
                confirm_phrase: phrase,
              });
              setNotice(
                `Deleted access #${res.access_id}` +
                  (res.snapshot_id ? ` · snapshot ${res.snapshot_id.slice(0, 8)}…` : ""),
              );
              setSelectedAccessId(null);
              setPane("new-access");
            } else {
              const res = await api.deleteRecordRule(connectionId, pendingDelete.id, {
                confirm_advanced: true,
                confirm_phrase: phrase,
              });
              setNotice(
                `Deleted rule #${res.rule_id}` +
                  (res.snapshot_id ? ` · snapshot ${res.snapshot_id.slice(0, 8)}…` : ""),
              );
              setSelectedRuleId(null);
              setPane("new-rule");
            }
            setPendingDelete(null);
            await refresh(model);
          } catch (err) {
            reportApiError(err, setError, { fallback: "Delete failed", toast: true });
          } finally {
            setBusy(false);
          }
        }}
      />
    </div>
  );
}
