"use client";

import { useParams } from "next/navigation";
import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { api, Connection } from "@/lib/api";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import {
  advancedMutationAllowed,
  advancedMutationBlockedReason,
  defaultWindowViewMode,
  mutationAllowed,
  mutationBlockedReason,
  connectionSupports,
} from "@/lib/capabilities";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Card, PageHeader } from "@/components/ui/layout-primitives";

const MENUS_REPORTS_CAVEAT =
  "Menus / QWeb reports are experimental on Odoo 16 — verify in Open-in-Odoo after create.";

const CONFIRM_PHRASE = "I understand the risks";

type MenuNode = {
  id: number;
  name: string;
  parent_id: number | null;
  action: string | null;
  action_id: number | null;
  sequence: number;
  web_icon: string | null;
  child_count: number;
};

type ActionRow = {
  id: number;
  name: string;
  res_model: string | null;
  view_mode: string | null;
};

export default function MenusBuilderPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [menus, setMenus] = useState<MenuNode[]>([]);
  const [actions, setActions] = useState<ActionRow[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [menuForm, setMenuForm] = useState({
    name: "",
    parent_id: "" as string,
    sequence: 10,
    web_icon: "base,static/description/icon.png",
  });
  const [actionForm, setActionForm] = useState({
    name: "",
    model: "res.partner",
    view_mode: "list,form",
  });
  const [bindActionId, setBindActionId] = useState("");

  const selected = useMemo(
    () => menus.find((m) => m.id === selectedId) ?? null,
    [menus, selectedId],
  );

  const refresh = useCallback(async () => {
    const [tree, acts] = await Promise.all([
      api.listMenuTree(connectionId),
      api.listWindowActions(connectionId),
    ]);
    setMenus(tree);
    setActions(acts);
  }, [connectionId]);

  useEffect(() => {
    api
      .getConnection(connectionId)
      .then(setConnection)
      .catch((err: Error) => setError(err.message));
  }, [connectionId]);

  useEffect(() => {
    if (!mutationAllowed(connection)) return;
    setActionForm((f) => ({
      ...f,
      view_mode: defaultWindowViewMode(connection),
    }));
  }, [connection]);

  useEffect(() => {
    refresh().catch((err: Error) => setError(err.message));
  }, [refresh]);

  const menusCaveat = useMemo(() => {
    if (
      mutationAllowed(connection) &&
      !connectionSupports(connection, "list_as_list_type")
    ) {
      return MENUS_REPORTS_CAVEAT;
    }
    return null;
  }, [connection]);

  const canMutate = mutationAllowed(connection);
  const mutateBlocked = mutationBlockedReason(connection);
  const canAdvanced = advancedMutationAllowed(connection);
  const advancedBlocked = advancedMutationBlockedReason(connection);

  const roots = menus.filter((m) => !m.parent_id);
  const childrenOf = (pid: number) =>
    menus.filter((m) => m.parent_id === pid).sort((a, b) => a.sequence - b.sequence);

  async function createMenu(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await api.createBuilderMenu(connectionId, {
        name: menuForm.name,
        parent_id: menuForm.parent_id ? Number(menuForm.parent_id) : null,
        sequence: menuForm.sequence,
        web_icon: menuForm.parent_id ? null : menuForm.web_icon,
      });
      setNotice(`Created menu #${created.id}`);
      setMenuForm((f) => ({ ...f, name: "" }));
      await refresh();
      setSelectedId(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  async function createAction(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const created = await api.createWindowAction(connectionId, actionForm);
      setNotice(`Created action #${created.id}`);
      setBindActionId(String(created.id));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action create failed");
    } finally {
      setBusy(false);
    }
  }

  function renderTree(nodes: MenuNode[], depth = 0): ReactNode {
    return nodes.map((m) => (
      <li key={m.id}>
        <button
          type="button"
          onClick={() => setSelectedId(m.id)}
          className={`flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-sm ${
            selectedId === m.id
              ? "bg-accent-subtle text-ink ring-1 ring-accent"
              : "text-muted hover:bg-surface-muted"
          }`}
          style={{ paddingLeft: 8 + depth * 14 }}
        >
          <span className="font-medium text-ink">{m.name}</span>
          <span className="font-mono text-[10px] text-muted">#{m.id}</span>
          {m.action_id ? (
            <span className="text-[10px] text-accent">act:{m.action_id}</span>
          ) : null}
        </button>
        <ul>{renderTree(childrenOf(m.id), depth + 1)}</ul>
      </li>
    ));
  }

  return (
    <div className="mx-auto max-w-6xl" data-testid="menus-page">
      <PageHeader
        title="Menus and actions"
        description="Visual tree for ir.ui.menu + ir.actions.act_window"
      />
      <VersionAwarenessBanner
        capabilities={connection?.capabilities}
        caveat={menusCaveat}
      />
      {mutateBlocked ? (
        <Callout variant="warning" title="Mutations blocked" className="mt-4">
          {mutateBlocked}
        </Callout>
      ) : null}

      {error ? <ErrorNotice message={error} className="mt-4" /> : null}
      {notice ? (
        <Callout variant="info" title="Notice" className="mt-4">
          {notice}
        </Callout>
      ) : null}

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_320px]">
        <Card className="p-4">
          <h2 className="text-sm font-semibold text-ink">Menu tree</h2>
          <ul className="mt-3 max-h-[28rem] overflow-auto">{renderTree(roots)}</ul>
        </Card>

        <div className="space-y-4">
          <Card className="p-4">
            <form onSubmit={createMenu} className="space-y-3">
              <h2 className="text-sm font-semibold text-ink">New menu</h2>
              <Input
                required
                value={menuForm.name}
                onChange={(e) => setMenuForm({ ...menuForm, name: e.target.value })}
                placeholder="Label"
              />
              <Select
                options={[
                  { value: "", label: "— root app —" },
                  ...menus.map((m) => ({
                    value: String(m.id),
                    label: `${m.name} (#${m.id})`,
                  })),
                ]}
                value={menuForm.parent_id}
                onChange={(e) => setMenuForm({ ...menuForm, parent_id: e.target.value })}
              />
              <Input
                type="number"
                value={String(menuForm.sequence)}
                onChange={(e) =>
                  setMenuForm({ ...menuForm, sequence: Number(e.target.value) })
                }
              />
              <Button
                type="submit"
                variant="primary"
                className="w-full"
                disabled={busy || !canMutate}
                title={mutateBlocked ?? undefined}
                loading={busy}
              >
                Create menu
              </Button>
            </form>
          </Card>

          <Card className="p-4">
            <form onSubmit={createAction} className="space-y-3">
              <h2 className="text-sm font-semibold text-ink">New window action</h2>
              <Input
                required
                value={actionForm.name}
                onChange={(e) => setActionForm({ ...actionForm, name: e.target.value })}
                placeholder="Action name"
              />
              <Input
                required
                value={actionForm.model}
                onChange={(e) => setActionForm({ ...actionForm, model: e.target.value })}
                placeholder="model"
                className="font-mono text-sm"
              />
              <Input
                value={actionForm.view_mode}
                onChange={(e) =>
                  setActionForm({ ...actionForm, view_mode: e.target.value })
                }
                className="font-mono text-sm"
              />
              <Button
                type="submit"
                variant="secondary"
                className="w-full"
                disabled={busy || !canMutate}
                title={mutateBlocked ?? undefined}
                loading={busy}
              >
                Create action
              </Button>
            </form>
          </Card>

          {selected ? (
            <Card className="space-y-3 p-4">
              <h2 className="text-sm font-semibold text-ink">Selected #{selected.id}</h2>
              <p className="text-xs text-muted">{selected.name}</p>
              <Select
                options={[
                  { value: "", label: "Bind action…" },
                  ...actions.map((a) => ({
                    value: String(a.id),
                    label: `#${a.id} ${a.name} (${a.res_model})`,
                  })),
                ]}
                value={bindActionId}
                onChange={(e) => setBindActionId(e.target.value)}
              />
              <Button
                type="button"
                variant="secondary"
                className="w-full"
                disabled={busy || !bindActionId || !canMutate}
                title={mutateBlocked ?? undefined}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await api.updateBuilderMenu(connectionId, selected.id, {
                      action_id: Number(bindActionId),
                    });
                    setNotice(`Bound action ${bindActionId}`);
                    await refresh();
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "Bind failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Bind action
              </Button>
              <Button
                type="button"
                variant="ghost"
                className="w-full text-danger"
                disabled={busy || !canAdvanced}
                title={advancedBlocked ?? undefined}
                onClick={() => setConfirmDelete(true)}
              >
                Delete menu
              </Button>
            </Card>
          ) : null}
        </div>
      </div>

      <ConfirmDialogV2
        open={confirmDelete}
        riskLevel="danger"
        title="Delete menu"
        warning="Removes this menu from Odoo."
        risks={["Child menus may cascade", "Action remains but is harder to find"]}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={async (phrase) => {
          if (!selected) return;
          setBusy(true);
          try {
            await api.deleteBuilderMenu(connectionId, selected.id, {
              confirm_advanced: true,
              confirm_phrase: phrase,
            });
            setConfirmDelete(false);
            setSelectedId(null);
            setNotice("Menu deleted");
            await refresh();
          } catch (err) {
            setError(err instanceof Error ? err.message : "Delete failed");
          } finally {
            setBusy(false);
          }
        }}
      />
    </div>
  );
}
