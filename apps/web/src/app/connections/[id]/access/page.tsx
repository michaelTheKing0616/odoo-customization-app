"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  AccessMatrixOut,
  AccessRightRow,
  api,
  ConfirmationRequiredError,
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
  connectionMajor,
  mutationAllowed,
  mutationBlockedReason,
} from "@/lib/capabilities";
import { Button } from "@/components/ui/Button";
import { OperateStudioChrome } from "@/components/operate-studio/OperateStudioChrome";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Disclosure } from "@/components/ui/Disclosure";
import { reportApiError } from "@/lib/api-error";
import { useSyncShellContext } from "@/lib/use-sync-shell-context";
import {
  ACCESS_DELETE_RISKS,
  CONFIRM_PHRASE,
  DEFAULT_ACCESS_MODEL,
  LIVE_PACK_RISKS,
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
import {
  accessScreenBranch,
  shouldOfferRecordRuleCreate,
} from "@/lib/accessMajor";
import {
  accessErrorGuide,
  accessHonestyGuide,
  accessSessionBadge,
  accessVersionFrame,
  accessWriteGate,
  groupLabel,
  normalizeMatrix,
  sanitizeAccessCopy,
  type AccessTab,
  type MatrixChange,
} from "@/lib/accessScreen";
import { AccessStateGuide } from "@/components/access/AccessStateGuide";
import { AccessVersionStrip } from "@/components/access/AccessVersionStrip";
import { AccessWorkspaceTabs } from "@/components/access/AccessWorkspaceTabs";
import "@/components/access/access-operate.css";
import { AccessComposer } from "@/components/access/AccessComposer";
import { AccessDetail } from "@/components/access/AccessDetail";
import { AccessExtras } from "@/components/access/AccessExtras";
import { AccessMatrixPanel } from "@/components/access/AccessMatrixPanel";
import { AccessModelPicker } from "@/components/access/AccessModelPicker";
import { AccessRightsList } from "@/components/access/AccessRightsList";
import { AccessSessionBar } from "@/components/access/AccessSessionBar";
import { ListComposerShell } from "@/components/ui/ListComposerShell";
import { AccessSnapshots } from "@/components/access/AccessSnapshots";
import { RecordRuleComposer } from "@/components/access/RecordRuleComposer";
import { RecordRuleDetail } from "@/components/access/RecordRuleDetail";
import { RecordRulesList } from "@/components/access/RecordRulesList";
import { ConnectionTeamGrantsPanel } from "@/components/access/ConnectionTeamGrantsPanel";

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
  const [listHydrated, setListHydrated] = useState(false);
  const [listLoading, setListLoading] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null);
  const [livePackOpen, setLivePackOpen] = useState(false);
  const [pane, setPane] = useState<AccessPane>("new-access");
  const [selectedAccessId, setSelectedAccessId] = useState<number | null>(null);
  const [selectedRuleId, setSelectedRuleId] = useState<number | null>(null);
  const [rightsQuery, setRightsQuery] = useState("");
  const [rulesQuery, setRulesQuery] = useState("");
  const [savedOnce, setSavedOnce] = useState(false);

  const [matrixModels, setMatrixModels] = useState(DEFAULT_ACCESS_MODEL);
  const [matrix, setMatrix] = useState<AccessMatrixOut | null>(null);
  const [matrixBusy, setMatrixBusy] = useState(false);
  const [matrixSaving, setMatrixSaving] = useState(false);
  const [tab, setTab] = useState<AccessTab>("matrix");
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
      const connP = api.getConnection(connectionId);
      const groupsP = api.listGroups(connectionId);
      const rightsP = api.listAccessRights(connectionId, target);
      const snapsP = api.listSnapshots(connectionId).catch(() => [] as SnapshotRow[]);
      const conn = await connP;
      const rulesP = accessScreenBranch(connectionMajor(conn)).fetchRecordRules
        ? api.listRecordRules(connectionId, target)
        : Promise.resolve([] as RecordRuleRow[]);
      const [gs, rs, rls, snaps] = await Promise.all([groupsP, rightsP, rulesP, snapsP]);
      setConnection(conn);
      setGroups(gs);
      setRights(rs);
      setRules(rls);
      setSnapshots(snaps);
    },
    [connectionId],
  );

  const loadMatrix = useCallback(
    async (models: string[], opts?: { quiet?: boolean }) => {
      if (models.length === 0) return;
      setMatrixBusy(true);
      if (!opts?.quiet) setError(null);
      try {
        const data = normalizeMatrix(await api.accessMatrix(connectionId, models));
        setMatrix(data);
      } catch (err) {
        if (!opts?.quiet) {
          reportApiError(err, setError, { fallback: "Matrix load failed", toast: true });
        }
      } finally {
        setMatrixBusy(false);
      }
    },
    [connectionId],
  );

  useEffect(() => {
    if (typeof window !== "undefined" && new URLSearchParams(window.location.search).get("model")) {
      // The ?model= effect below owns the first load.
    } else {
      setListLoading(true);
      refresh(DEFAULT_ACCESS_MODEL)
        .then(() => loadMatrix([DEFAULT_ACCESS_MODEL], { quiet: true }))
        .catch((err: Error) => setError(err.message))
        .finally(() => {
          setListLoading(false);
          setListHydrated(true);
        });
    }
    api.getMultiCompanyGuidance(connectionId).then(setMcGuidance).catch(() => {});
    api
      .getDocumentsGate(connectionId)
      .then((g) => setDocsGate({ available: g.available, message: g.message }))
      .catch(() => setDocsGate({ available: false }));
    api
      .getDocumentsFolderMap(connectionId)
      .then((m) => setDocsMapping(m.mapping))
      .catch(() => {});
  }, [refresh, loadMatrix, connectionId]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const fromQuery = new URLSearchParams(window.location.search).get("model");
    if (!fromQuery) return;
    setModel(fromQuery);
    setMatrixModels(fromQuery);
    setListLoading(true);
    refresh(fromQuery)
      .then(() => loadMatrix(parseModelList(fromQuery), { quiet: true }))
      .catch((err: Error) => setError(err.message))
      .finally(() => {
        setListLoading(false);
        setListHydrated(true);
      });
  }, [refresh, loadMatrix]);

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
    if (!shouldOfferRecordRuleCreate(connectionMajor(connection))) {
      return;
    }
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

  /** Primary action: save the staged rights. Sequential so a failure stops cleanly. */
  async function saveMatrix(changes: MatrixChange[]): Promise<boolean> {
    if (accessWriteGate(connection, connectionId).mode !== "inline" || changes.length === 0) {
      return false;
    }
    setMatrixSaving(true);
    setError(null);
    setNotice(null);
    const groupsForNames = matrix?.groups ?? groups;
    let done = 0;
    try {
      for (const change of changes) {
        if (change.accessId) {
          await api.updateAccessRight(connectionId, change.accessId, change.patch);
        } else {
          await api.createAccessRight(connectionId, {
            model: change.model,
            name: `${change.model} / ${groupLabel(groupsForNames, change.groupId)}`,
            group_id: change.groupId,
            ...change.after,
          });
        }
        done += 1;
      }
      setNotice(
        `Saved ${changes.length} ${changes.length === 1 ? "right" : "rights"} to Odoo. A snapshot was taken first.`,
      );
      setSavedOnce(true);
      await loadMatrix(parseModelList(matrixModels), { quiet: true });
      await refresh(model).catch(() => undefined);
      return true;
    } catch (err) {
      reportApiError(err, setError, { fallback: "Save failed", toast: true });
      if (done > 0) {
        setNotice(`Saved ${done} of ${changes.length} rights before Odoo stopped. Review the matrix.`);
        await loadMatrix(parseModelList(matrixModels), { quiet: true });
      }
      return false;
    } finally {
      setMatrixSaving(false);
    }
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

  const gate = accessWriteGate(connection, connectionId);
  const inline = gate.mode === "inline";
  const planHref = gate.mode === "plan" ? gate.planHref : null;
  const canMutate = mutationAllowed(connection) && inline;
  const mutateBlocked = mutationBlockedReason(connection) ?? (inline ? null : gate.title);
  const canAdvanced = advancedMutationAllowed(connection) && inline;
  const advancedBlocked = advancedMutationBlockedReason(connection) ?? (inline ? null : gate.title);
  const deleteOnlyBlocked = inline ? advancedMutationBlockedReason(connection) : null;

  const selectedAccess = rights.find((r) => r.id === selectedAccessId) ?? null;
  const selectedRule = rules.find((r) => r.id === selectedRuleId) ?? null;
  const accessDirty = isComposerDirty(accessForm, accessBaseline);
  const ruleDirty = isComposerDirty(ruleForm, ruleBaseline);
  const major = connectionMajor(connection);
  const accessBranch = accessScreenBranch(major);
  const frame = accessVersionFrame(major);
  const activeTab: AccessTab = frame.tabs.includes(tab) ? tab : "matrix";
  const composingAccess = pane === "new-access";
  const composingRule = pane === "new-rule" && accessBranch.offerRecordRuleCreate;
  const sessionState = composerSessionState({
    dirty: composingAccess ? accessDirty : composingRule ? ruleDirty : false,
    savedOnce,
  });
  const errorGuide = error ? accessErrorGuide(error, model) : null;

  function selectTab(next: AccessTab) {
    setTab(next);
    setNotice(null);
    if (next === "rules" && pane !== "rule") {
      setSelectedAccessId(null);
      setPane("new-rule");
    }
    if (next === "lines" && pane !== "access") {
      setSelectedRuleId(null);
      setPane("new-access");
    }
  }

  const modelPicker = (
    <AccessModelPicker model={model} onModelChange={setModel} onLoad={onLoadModel} busy={busy} />
  );

  const accessDetailPane =
    pane === "access" && selectedAccess ? (
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
        planHref={planHref}
        onSave={async (patch) => {
          setBusy(true);
          setError(null);
          try {
            await api.updateAccessRight(connectionId, selectedAccess.id, patch);
            setNotice(`Saved access #${selectedAccess.id} to Odoo.`);
            await refresh(model);
            await loadMatrix(parseModelList(matrixModels), { quiet: true });
          } catch (err) {
            reportApiError(err, setError, { fallback: "Save failed", toast: true });
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
    ) : (
      <>
        <AccessSessionBar
          sessionState={sessionState}
          busy={busy}
          canDiscard={accessDirty}
          submitLabel={planHref ? "Plan card" : "Save right"}
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
          planHref={planHref}
        />
      </>
    );

  const ruleDetailPane =
    pane === "rule" && selectedRule ? (
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
        planHref={planHref}
        onSave={async (patch) => {
          setBusy(true);
          setError(null);
          try {
            await api.updateRecordRule(connectionId, selectedRule.id, patch);
            setNotice(`Saved rule #${selectedRule.id} to Odoo.`);
            await refresh(model);
          } catch (err) {
            reportApiError(err, setError, { fallback: "Save failed", toast: true });
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
    ) : (
      <>
        <AccessSessionBar
          sessionState={sessionState}
          busy={busy}
          canDiscard={ruleDirty}
          submitLabel={planHref ? "Plan card" : "Save rule"}
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
          planHref={planHref}
        />
      </>
    );

  const accessMode = gate?.mode ?? "inline";
  const honesty = accessHonestyGuide({ mode: accessMode });

  return (
    <OperateStudioChrome
      testIdPrefix="access"
      pageTestId="access-page"
      kicker={connection?.name ?? connectionId}
      title="Access"
      subtitle="Who can read, write, create and delete each model."
      badge={accessSessionBadge({ mode: accessMode, unsaved: false })}
      honesty={honesty}
      sanitize={sanitizeAccessCopy}
      shellClassName="access-operate"
      className="p-4 sm:p-6"
      titleActions={
        <>
          <ExplainThisButton
            question={`Explain access rights and record rules for model ${model}`}
            label="Explain access"
          />
          <Button variant="secondary" size="sm" asChild>
            <Link href={designerHref(connectionId, model)} data-testid="access-designer-link">
              Open in View Designer
            </Link>
          </Button>
        </>
      }
    >
      <AccessVersionStrip frame={frame} gate={gate} />
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
      {gate.mode !== "inline" && listHydrated ? (
        <AccessStateGuide
          guide={gate}
          tone={gate.mode === "plan" ? "warning" : "neutral"}
          testId="access-gate"
          className="mt-4"
        />
      ) : null}
      {deleteOnlyBlocked ? (
        <AccessStateGuide
          guide={{
            title: "Deletes are off on this Odoo",
            why: deleteOnlyBlocked,
            next: "Saves still work. Delete lines from a GA Odoo major.",
          }}
          testId="access-delete-gate"
          className="mt-4"
        />
      ) : null}
      {errorGuide ? (
        <AccessStateGuide
          guide={errorGuide}
          tone="danger"
          live
          testId="access-error"
          className="mt-4"
          actions={
            <Button
              type="button"
              variant="secondary"
              size="sm"
              data-testid="access-error-retry"
              onClick={() => {
                setError(null);
                setListLoading(true);
                void refresh(model)
                  .then(() => loadMatrix(parseModelList(matrixModels), { quiet: true }))
                  .catch((err: Error) => setError(err.message))
                  .finally(() => setListLoading(false));
              }}
            >
              Retry
            </Button>
          }
        />
      ) : null}
      {notice ? (
        <p className="ax-notice" role="status" data-testid="access-notice">
          {notice}
        </p>
      ) : null}

      <AccessWorkspaceTabs
        tabs={frame.tabs}
        value={activeTab}
        onChange={selectTab}
        counts={{ lines: rights.length, rules: rules.length }}
      >
        {activeTab === "matrix" ? (
          <AccessMatrixPanel
            frame={frame}
            gate={gate}
            modelsInput={matrixModels}
            onModelsInput={setMatrixModels}
            matrix={matrix}
            loading={matrixBusy}
            saving={matrixSaving}
            onLoad={() => void loadMatrix(parseModelList(matrixModels))}
            onSave={saveMatrix}
          />
        ) : activeTab === "rules" && accessBranch.offerRecordRuleCreate ? (
          <ListComposerShell
            className="!mt-0"
            list={
              <div className="grid gap-6">
                {modelPicker}
                <RecordRulesList
                  rows={rules}
                  model={model}
                  loading={!listHydrated || listLoading}
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
              </div>
            }
            detail={ruleDetailPane}
          />
        ) : (
          <ListComposerShell
            className="!mt-0"
            list={
              <div className="grid gap-6">
                {modelPicker}
                <AccessRightsList
                  rows={rights}
                  model={model}
                  title={frame.combined ? "ir.access rows" : "Access lines"}
                  loading={!listHydrated || listLoading}
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
                <AccessSnapshots
                  connectionId={connectionId}
                  snapshots={snapshots}
                  busy={busy}
                  onRollback={onRollback}
                />
              </div>
            }
            detail={accessDetailPane}
          />
        )}
      </AccessWorkspaceTabs>

      <Disclosure title="Client access grants" className="mt-10" testId="connection-team-grants-disclosure">
        <ConnectionTeamGrantsPanel
          connectionId={connectionId}
          connectionName={connection?.name}
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
          onApplyMultiCompany={() => {
            setError(null);
            if (!inline) {
              // The live pack writes a global ir.rule: same R3 gate as every access write.
              setNotice(`${gate.title}. ${gate.next}`);
              return;
            }
            setLivePackOpen(true);
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
        blastRadius={
          pendingDelete
            ? [
                `${pendingDelete.kind === "access" ? "Access right" : "Record rule"}: ${pendingDelete.name}`,
                `Model ${model}`,
                "Live Odoo metadata delete",
              ]
            : []
        }
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

      <ConfirmDialogV2
        open={livePackOpen}
        riskLevel="danger"
        title="Apply live pack"
        warning={`Creates x_company_id and a global ir.rule on ${model}. This writes live Odoo metadata.`}
        risks={LIVE_PACK_RISKS}
        blastRadius={[
          `Model ${model}`,
          "Creates x_company_id when missing",
          "Creates a global ir.rule for multi-company",
        ]}
        phrase={CONFIRM_PHRASE}
        snapshotNote="Field and record-rule creates are only partially recoverable."
        busy={busy}
        onCancel={() => setLivePackOpen(false)}
        onConfirm={async (phrase) => {
          setBusy(true);
          setError(null);
          setNotice(null);
          try {
            const res = await api.applyMultiCompanyLive(connectionId, [model], {
              confirm_advanced: true,
              confirm_phrase: phrase,
            });
            setNotice(
              `Multi-company: ${res.fields_created} field(s), ${res.rules_created} rule(s)` +
                (res.warnings.length ? ` · ${res.warnings.join("; ")}` : ""),
            );
            setLivePackOpen(false);
            await refresh(model);
          } catch (err) {
            if (err instanceof ConfirmationRequiredError) {
              setError(err.warning || err.message);
            } else {
              reportApiError(err, setError, {
                fallback: "Multi-company apply failed",
                toast: true,
              });
            }
          } finally {
            setBusy(false);
          }
        }}
      />
    </OperateStudioChrome>
  );
}