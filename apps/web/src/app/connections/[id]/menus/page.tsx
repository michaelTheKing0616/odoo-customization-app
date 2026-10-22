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
import { OperateStudioChrome } from "@/components/operate-studio/OperateStudioChrome";
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
  wouldCreateCycle,
  type MenuComposerForm,
} from "@/lib/menuForm";
import { applyDraftParent, menusErrorGuide, type MenusErrorContext } from "@/lib/menuTree";
import { MenuComposer } from "@/components/menus/MenuComposer";
import { MenuDetail } from "@/components/menus/MenuDetail";
import { MenuSessionBar } from "@/components/menus/MenuSessionBar";
import { MenuSnapshots } from "@/components/menus/MenuSnapshots";
import { MenusStateGuide } from "@/components/menus/MenusStateGuide";
import { MenusTree } from "@/components/menus/MenusTree";
import { ListComposerShell } from "@/components/ui/ListComposerShell";
import {
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  menusHonestyGuide,
  menusSessionBadge,
  sanitizeMenusCopy,
} from "@/lib/menusScreen";
import "@/components/menus/menus-operate.css";

type DraftParent = { menuId: number; value: string };

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
  const [errorContext, setErrorContext] = useState<MenusErrorContext>("load");
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [listHydrated, setListHydrated] = useState(false);
  const [listLoading, setListLoading] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [savedOnce, setSavedOnce] = useState(false);
  const [draftParent, setDraftParent] = useState<DraftParent | null>(null);

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

  const fail = useCallback((context: MenusErrorContext, message: string | null) => {
    setErrorContext(context);
    setError(message);
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

  const reload = useCallback(() => {
    setListLoading(true);
    setError(null);
    return refresh()
      .catch((err: Error) => fail("load", err.message))
      .finally(() => {
        setListLoading(false);
        setListHydrated(true);
      });
  }, [refresh, fail]);

  useEffect(() => {
    api
      .getConnection(connectionId)
      .then(setConnection)
      .catch((err: Error) => fail("load", err.message));
  }, [connectionId, fail]);

  useEffect(() => {
    void reload();
  }, [reload]);

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

  /** The tree shows a staged parent change in place, marked as unsaved. */
  const stagedMove = useMemo(() => {
    if (!draftParent) return null;
    const parentId = draftParent.value ? Number(draftParent.value) : null;
    if (wouldCreateCycle(menus, draftParent.menuId, parentId)) return null;
    return { menuId: draftParent.menuId, parentId };
  }, [draftParent, menus]);
  const treeMenus = useMemo(() => applyDraftParent(menus, stagedMove), [menus, stagedMove]);

  function selectMenu(id: number | null) {
    setSelectedId(id);
    setNotice(null);
    setDraftParent((d) => (d && d.menuId === id ? d : null));
  }

  function discardComposer() {
    setForm(baseline);
    setSelectedId(null);
  }

  function startNew() {
    selectMenu(null);
    if (typeof document !== "undefined") {
      window.requestAnimationFrame(() => document.getElementById("menu-new-label")?.focus());
    }
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
      setNotice(`Created “${created.name || form.name.trim()}” on Odoo as menu #${created.id}.`);
      setSavedOnce(true);
      const next = { ...form, name: "", action_name: "" };
      setForm(next);
      setBaseline(next);
      await refresh();
      setSelectedId(created.id);
    } catch (err) {
      reportApiError(err, (m) => fail("create", m), { fallback: "Create failed", toast: true });
    } finally {
      setBusy(false);
    }
  }

  async function onRollback(snapshotId: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await api.rollbackSnapshot(connectionId, snapshotId);
      setNotice(`Restored ${res.restored} #${res.id} from the snapshot.`);
      await refresh();
    } catch (err) {
      reportApiError(err, (m) => fail("restore", m), { fallback: "Rollback failed", toast: true });
    } finally {
      setBusy(false);
    }
  }

  const guide = error ? menusErrorGuide(errorContext, error) : null;

  const honesty = menusHonestyGuide();

  return (
    <OperateStudioChrome
      testIdPrefix="menus"
      pageTestId="menus-page"
      kicker={connection?.name ?? connectionId}
      title={PAGE_TITLE}
      subtitle={PAGE_DESCRIPTION}
      badge={menusSessionBadge({ unsaved: false, empty: false })}
      honesty={honesty}
      sanitize={sanitizeMenusCopy}
      shellClassName="menus-operate"
      className="p-4 sm:p-6"
      titleActions={
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
    >
      <p className="mn-intro">
        Top-level menus need an icon file path on Odoo 19. Bind a standalone window action so each
        item opens a model. Smart-button actions that need active_id stay off this tree.
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
              fail("probe", err instanceof Error ? err.message : "Probe failed");
            } finally {
              setProbing(false);
            }
          })();
        }}
      />

      {mutateBlocked ? (
        <Callout variant="warning" title="Changes are switched off" className="mt-4">
          {mutateBlocked}
        </Callout>
      ) : null}

      {guide ? (
        <MenusStateGuide
          guide={guide}
          tone="danger"
          live
          className="mt-4"
          testId="menus-error"
          actions={
            errorContext === "load" ? (
              <Button type="button" variant="secondary" size="sm" onClick={() => void reload()}>
                Try again
              </Button>
            ) : (
              <Button type="button" variant="ghost" size="sm" onClick={() => setError(null)}>
                Dismiss
              </Button>
            )
          }
        />
      ) : null}
      {notice ? (
        <p className="mn-notice" role="status" data-testid="menus-notice">
          {notice}
        </p>
      ) : null}

      <ListComposerShell
        list={
          <>
            <MenusTree
              menus={treeMenus}
              actions={actions}
              loading={!listHydrated || listLoading}
              selectedId={selectedId}
              query={listQuery}
              onQueryChange={setListQuery}
              onSelect={(menu) => selectMenu(menu.id)}
              onCreate={startNew}
              onMove={(menu, parentId) => {
                setSelectedId(menu.id);
                setNotice(null);
                setDraftParent({ menuId: menu.id, value: parentId == null ? "" : String(parentId) });
              }}
              canMove={canMutate}
              moveBlockedReason={mutateBlocked}
              stagedMenuId={stagedMove?.menuId ?? null}
              unavailable={Boolean(error) && errorContext === "load"}
            />
            <MenuSnapshots
              connectionId={connectionId}
              snapshots={snapshots}
              busy={busy}
              onRollback={onRollback}
            />
          </>
        }
        detail={
          selected ? (
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
              parentValue={
                draftParent?.menuId === selected.id
                  ? draftParent.value
                  : selected.parent_id != null
                    ? String(selected.parent_id)
                    : ""
              }
              onParentChange={(value) => {
                const original = selected.parent_id != null ? String(selected.parent_id) : "";
                setDraftParent(value === original ? null : { menuId: selected.id, value });
              }}
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
                    ...(patch.web_icon ? { web_icon: patch.web_icon } : {}),
                  });
                  setNotice(`Saved “${patch.name}” to Odoo.`);
                  setDraftParent(null);
                  await refresh();
                } catch (err) {
                  reportApiError(err, (m) => fail("save", m), { fallback: "Update failed", toast: true });
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
                  setNotice(`Created action #${created.id} and bound it to “${selected.name}”.`);
                  await refresh();
                } catch (err) {
                  reportApiError(err, (m) => fail("bind", m), { fallback: "Action create failed", toast: true });
                } finally {
                  setBusy(false);
                }
              }}
              onDelete={() => setConfirmDelete(true)}
            />
          ) : (
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
              sessionBar={
                <MenuSessionBar
                  className="mn-session-inline"
                  sessionState={sessionState}
                  busy={busy}
                  canDiscard={dirty}
                  submitLabel="Create menu"
                  onDiscard={discardComposer}
                />
              }
            />
          )
        }
      />

      <ConfirmDialogV2
        open={confirmDelete}
        riskLevel="danger"
        title="Delete menu"
        warning="Removes this menu from Odoo's app switcher and navbar."
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
            setDraftParent(null);
            setNotice(
              `Deleted “${selected.name}”.` +
                (res.snapshot_id ? ` Snapshot ${res.snapshot_id.slice(0, 8)} can restore it.` : ""),
            );
            await refresh();
          } catch (err) {
            reportApiError(err, (m) => fail("delete", m), { fallback: "Delete failed", toast: true });
          } finally {
            setBusy(false);
          }
        }}
      />
    </OperateStudioChrome>
  );
}