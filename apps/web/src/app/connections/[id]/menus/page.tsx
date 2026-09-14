"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api, Connection, GroupRow, MenuNode, SnapshotRow, WindowActionRow } from "@/lib/api";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { CapabilityProbePanel } from "@/components/CapabilityProbePanel";
import { ExplainThisButton } from "@/components/expert/ExplainThisButton";
import {
  advancedMutationAllowed,
  advancedMutationBlockedReason,
  connectionSupports,
  defaultWindowViewMode,
  mutationAllowed,
  mutationBlockedReason,
} from "@/lib/capabilities";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { PageHeader } from "@/components/ui/layout-primitives";
import { reportApiError } from "@/lib/api-error";
import { useSyncShellContext } from "@/lib/use-sync-shell-context";
import {
  CONFIRM_PHRASE,
  MENUS_REPORTS_CAVEAT,
  MENU_DELETE_RISKS,
  boundAction,
  composerSessionState,
  defaultMenuForm,
  designerHref,
  isComposerDirty,
  type MenuComposerForm,
} from "@/lib/menuForm";
import { MenuComposer } from "@/components/menus/MenuComposer";
import { MenuDetail } from "@/components/menus/MenuDetail";
import { MenuSessionBar } from "@/components/menus/MenuSessionBar";
import { MenuSnapshots } from "@/components/menus/MenuSnapshots";
import { MenusTree } from "@/components/menus/MenusTree";

export default function MenusBuilderPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [probing, setProbing] = useState(false);
  const [menus, setMenus] = useState<MenuNode[]>([]);
  const [actions, setActions] = useState<WindowActionRow[]>([]);
  const [groups, setGroups] = useState<GroupRow[]>([]);
  const [snapshots, setSnapshots] = useState<SnapshotRow[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [listQuery, setListQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [listLoading, setListLoading] = useState(true);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [savedOnce, setSavedOnce] = useState(false);

  const viewMode = defaultWindowViewMode(connection);
  const [form, setForm] = useState<MenuComposerForm>(() => defaultMenuForm(viewMode));
  const [baseline, setBaseline] = useState<MenuComposerForm>(() => defaultMenuForm(viewMode));

  useSyncShellContext({
    model: form.action_model,
    draftSummary: form.name || undefined,
  });

  const patchForm = useCallback((next: Partial<MenuComposerForm>) => {
    setForm((f) => ({ ...f, ...next }));
  }, []);

  const refresh = useCallback(async () => {
    const [tree, acts, gs, snaps] = await Promise.all([
      api.listMenuTree(connectionId),
      api.listWindowActions(connectionId),
      api.listGroups(connectionId).catch(() => [] as GroupRow[]),
      api.listSnapshots(connectionId).catch(() => [] as SnapshotRow[]),
    ]);
    setMenus(tree);
    setActions(acts);
    setGroups(gs);
    setSnapshots(snaps);
  }, [connectionId]);

  useEffect(() => {
    api
      .getConnection(connectionId)
      .then(setConnection)
      .catch((err: Error) => setError(err.message));
  }, [connectionId]);

  useEffect(() => {
    setListLoading(true);
    refresh()
      .catch((err: Error) => setError(err.message))
      .finally(() => setListLoading(false));
  }, [refresh]);

  useEffect(() => {
    const next = defaultWindowViewMode(connection);
    setForm((f) => (f.action_view_mode === next ? f : { ...f, action_view_mode: next }));
    setBaseline((b) => (b.action_view_mode === next ? b : { ...b, action_view_mode: next }));
  }, [connection]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const fromQuery = new URLSearchParams(window.location.search).get("model");
    if (!fromQuery) return;
    setForm((f) => ({ ...f, action_model: fromQuery, action_mode: "create" }));
    setBaseline((b) => ({ ...b, action_model: fromQuery, action_mode: "create" }));
  }, []);

  const menusCaveat = useMemo(() => {
    if (mutationAllowed(connection) && !connectionSupports(connection, "list_as_list_type")) {
      return MENUS_REPORTS_CAVEAT;
    }
    return null;
  }, [connection]);

  const canMutate = mutationAllowed(connection);
  const mutateBlocked = mutationBlockedReason(connection);
  const canAdvanced = advancedMutationAllowed(connection);
  const advancedBlocked = advancedMutationBlockedReason(connection);

  const selected = menus.find((m) => m.id === selectedId) ?? null;
  const dirty = isComposerDirty(form, baseline);
  const sessionState = composerSessionState({ dirty, savedOnce });
  const bound = selected ? boundAction(actions, selected.action_id) : null;

  function discardComposer() {
    setForm(baseline);
    setSelectedId(null);
  }

  function startNew() {
    setSelectedId(null);
    setNotice(null);
  }

  async function createMenu(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      let actionId = form.action_id ? Number(form.action_id) : null;
      if (form.action_mode === "create") {
        const createdAction = await api.createWindowAction(connectionId, {
          name: form.action_name || `${form.name} list`,
          model: form.action_model,
          view_mode: form.action_view_mode,
        });
        actionId = createdAction.id;
      }
      const created = await api.createBuilderMenu(connectionId, {
        name: form.name.trim(),
        parent_id: form.parent_id ? Number(form.parent_id) : null,
        sequence: form.sequence,
        web_icon: form.parent_id ? null : form.web_icon,
        action_id: actionId,
        group_ids: form.group_ids,
      });
      setNotice(`Created menu #${created.id}`);
      setSavedOnce(true);
      const next = { ...form, name: "", action_name: "" };
      setForm(next);
      setBaseline(next);
      await refresh();
      setSelectedId(created.id);
    } catch (err) {
      reportApiError(err, setError, { fallback: "Create failed", toast: true });
    } finally {
      setBusy(false);
    }
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

  return (
    <div className="mx-auto max-w-6xl" data-testid="menus-page">
      <PageHeader
        title="Menus"
        description={`${connection?.name ?? connectionId} · Tree, parent, sequence, action binding, and visibility groups.`}
        actions={
          <>
            <Button variant="secondary" size="sm" asChild>
              <Link
                href={designerHref(connectionId, bound?.res_model || form.action_model)}
                data-testid="menus-designer-link"
              >
                Open in View Designer
              </Link>
            </Button>
            <ExplainThisButton
              question={`Explain ir.ui.menu and window actions for ${form.action_model || "this instance"}`}
              label="Explain menus"
            />
          </>
        }
      />
      <p className="mt-2 text-sm text-muted">
        Root menus need a file-path icon on Odoo 19. Bind a standalone window action so the item
        opens a model — related-button actions that need active_id stay off this tree.
      </p>
      <VersionAwarenessBanner
        capabilities={connection?.capabilities}
        caveat={menusCaveat}
        className="mt-4"
      />
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

      {error ? (
        <ErrorNotice message={error} className="mt-4" onRetry={() => void refresh()} />
      ) : null}
      {notice ? (
        <Callout variant="info" title="Notice" className="mt-4">
          {notice}
        </Callout>
      ) : null}

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(240px,320px)_minmax(0,1fr)]">
        <div>
          <MenusTree
            menus={menus}
            loading={listLoading}
            selectedId={selectedId}
            query={listQuery}
            onQueryChange={setListQuery}
            onSelect={(menu) => {
              setSelectedId(menu.id);
              setNotice(null);
            }}
            onCreate={startNew}
          />
          <MenuSnapshots
            connectionId={connectionId}
            snapshots={snapshots}
            busy={busy}
            onRollback={onRollback}
          />
        </div>

        <div className="space-y-4">
          {selected ? (
            <MenuDetail
              key={selected.id}
              connectionId={connectionId}
              menu={selected}
              menus={menus}
              actions={actions}
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
                  await api.updateBuilderMenu(connectionId, selected.id, {
                    name: patch.name,
                    parent_id: patch.parent_id,
                    clear_parent: patch.clear_parent,
                    sequence: patch.sequence,
                    action_id: patch.action_id,
                    clear_action: patch.clear_action,
                    group_ids: patch.group_ids,
                    clear_groups: patch.clear_groups,
                  });
                  setNotice(`Updated menu #${selected.id}`);
                  await refresh();
                } catch (err) {
                  reportApiError(err, setError, { fallback: "Update failed", toast: true });
                } finally {
                  setBusy(false);
                }
              }}
              onCreateAndBind={async ({ name, model, view_mode }) => {
                setBusy(true);
                setError(null);
                try {
                  const created = await api.createWindowAction(connectionId, {
                    name,
                    model,
                    view_mode,
                  });
                  await api.updateBuilderMenu(connectionId, selected.id, {
                    action_id: created.id,
                  });
                  setNotice(`Bound action #${created.id}`);
                  await refresh();
                } catch (err) {
                  reportApiError(err, setError, { fallback: "Action create failed", toast: true });
                } finally {
                  setBusy(false);
                }
              }}
              onDelete={() => setConfirmDelete(true)}
            />
          ) : (
            <>
              <MenuSessionBar
                sessionState={sessionState}
                busy={busy}
                canDiscard={dirty}
                submitLabel="Create menu"
                onDiscard={discardComposer}
              />
              <MenuComposer
                form={form}
                menus={menus}
                actions={actions}
                groups={groups}
                onChange={patchForm}
                onSubmit={createMenu}
                busy={busy}
                canSubmit={canMutate}
                submitBlockedReason={mutateBlocked}
              />
            </>
          )}
        </div>
      </div>

      <ConfirmDialogV2
        open={confirmDelete}
        riskLevel="danger"
        title="Delete menu"
        warning="Removes this menu from the Odoo app switcher / navbar."
        risks={MENU_DELETE_RISKS}
        phrase={CONFIRM_PHRASE}
        snapshotNote="A snapshot is taken so the menu definition can be restored when Odoo allows it."
        busy={busy}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={async (phrase) => {
          if (!selected) return;
          setBusy(true);
          try {
            const res = await api.deleteBuilderMenu(connectionId, selected.id, {
              confirm_advanced: true,
              confirm_phrase: phrase,
            });
            setConfirmDelete(false);
            setSelectedId(null);
            setNotice(
              `Deleted menu #${selected.id}` +
                (res.snapshot_id ? ` · snapshot ${res.snapshot_id.slice(0, 8)}…` : ""),
            );
            await refresh();
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
