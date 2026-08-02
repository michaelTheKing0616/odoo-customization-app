"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { api, Connection } from "@/lib/api";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import {
  advancedMutationAllowed,
  advancedMutationBlockedReason,
  defaultWindowViewMode,
  mutationAllowed,
  mutationBlockedReason,
  connectionSupports,
} from "@/lib/capabilities";

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
    // tree-era majors (no list_as_list_type) — same surface caveat as Reports
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
          className={`flex w-full items-center gap-2 px-2 py-1 text-left text-sm ${
            selectedId === m.id
              ? "bg-[var(--odoo-primary)]/20 text-[#faf6f9]"
              : "text-[#d4c4ce] hover:bg-[#1a2e28]"
          }`}
          style={{ paddingLeft: 8 + depth * 14 }}
        >
          <span className="font-medium">{m.name}</span>
          <span className="font-mono text-[10px] text-[#8f7a88]">#{m.id}</span>
          {m.action_id && (
            <span className="text-[10px] text-[#c9a9c0]">act:{m.action_id}</span>
          )}
        </button>
        <ul>{renderTree(childrenOf(m.id), depth + 1)}</ul>
      </li>
    ));
  }

  return (
    <main className="odoo-shell min-h-screen px-6 py-10">
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-wrap gap-4 text-sm">
          <Link href={`/connections/${connectionId}`} className="text-[#c9a9c0] hover:underline">
            ← Metadata
          </Link>
          <Link
            href={`/connections/${connectionId}/config`}
            className="text-[#8f7a88] hover:underline"
          >
            Settings
          </Link>
        </div>
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl text-[#faf6f9]">
          Menus &amp; actions
        </h1>
        <p className="mt-1 text-sm text-[#8f7a88]">
          Visual tree for <code>ir.ui.menu</code> + <code>ir.actions.act_window</code>
        </p>
        <VersionAwarenessBanner
          capabilities={connection?.capabilities}
          caveat={menusCaveat}
        />
        {mutateBlocked && (
          <p className="mt-2 text-sm text-[#e8d09f]">{mutateBlocked}</p>
        )}

        {error && <p className="mt-4 text-sm text-[#f0a8a0]">{error}</p>}
        {notice && <p className="mt-4 text-sm text-[#c9a9c0]">{notice}</p>}

        <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_320px]">
          <div className="border border-[#3d2a38] bg-[#0f1a16]/70 p-4">
            <h2 className="text-sm font-semibold text-[#c9a9c0]">Menu tree</h2>
            <ul className="mt-3 max-h-[28rem] overflow-auto">{renderTree(roots)}</ul>
          </div>

          <div className="space-y-4">
            <form
              onSubmit={createMenu}
              className="space-y-2 border border-[#3d2a38] bg-[#0f1a16]/70 p-4"
            >
              <h2 className="text-sm font-semibold">New menu</h2>
              <input
                required
                value={menuForm.name}
                onChange={(e) => setMenuForm({ ...menuForm, name: e.target.value })}
                placeholder="Label"
                className="w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-sm"
              />
              <select
                value={menuForm.parent_id}
                onChange={(e) => setMenuForm({ ...menuForm, parent_id: e.target.value })}
                className="w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-sm"
              >
                <option value="">— root app —</option>
                {menus.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} (#{m.id})
                  </option>
                ))}
              </select>
              <input
                type="number"
                value={menuForm.sequence}
                onChange={(e) =>
                  setMenuForm({ ...menuForm, sequence: Number(e.target.value) })
                }
                className="w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-sm"
              />
              <button
                type="submit"
                disabled={busy || !canMutate}
                title={mutateBlocked ?? undefined}
                className="h-9 w-full bg-[#714B67] text-sm font-semibold text-white disabled:opacity-50"
              >
                Create menu
              </button>
            </form>

            <form
              onSubmit={createAction}
              className="space-y-2 border border-[#3d2a38] bg-[#0f1a16]/70 p-4"
            >
              <h2 className="text-sm font-semibold">New window action</h2>
              <input
                required
                value={actionForm.name}
                onChange={(e) => setActionForm({ ...actionForm, name: e.target.value })}
                placeholder="Action name"
                className="w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-sm"
              />
              <input
                required
                value={actionForm.model}
                onChange={(e) => setActionForm({ ...actionForm, model: e.target.value })}
                placeholder="model"
                className="w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 font-mono text-sm"
              />
              <input
                value={actionForm.view_mode}
                onChange={(e) =>
                  setActionForm({ ...actionForm, view_mode: e.target.value })
                }
                className="w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 font-mono text-sm"
              />
              <button
                type="submit"
                disabled={busy || !canMutate}
                title={mutateBlocked ?? undefined}
                className="h-9 w-full border border-[#c9a9c0] text-sm text-[#c9a9c0] disabled:opacity-50"
              >
                Create action
              </button>
            </form>

            {selected && (
              <div className="space-y-2 border border-[#3d2a38] bg-[#0f1a16]/70 p-4">
                <h2 className="text-sm font-semibold">Selected #{selected.id}</h2>
                <p className="text-xs text-[#8f7a88]">{selected.name}</p>
                <select
                  value={bindActionId}
                  onChange={(e) => setBindActionId(e.target.value)}
                  className="w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-sm"
                >
                  <option value="">Bind action…</option>
                  {actions.map((a) => (
                    <option key={a.id} value={a.id}>
                      #{a.id} {a.name} ({a.res_model})
                    </option>
                  ))}
                </select>
                <button
                  type="button"
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
                  className="h-9 w-full border border-[#c9a9c0] text-sm text-[#c9a9c0] disabled:opacity-50"
                >
                  Bind action
                </button>
                <button
                  type="button"
                  disabled={busy || !canAdvanced}
                  title={advancedBlocked ?? undefined}
                  onClick={() => setConfirmDelete(true)}
                  className="h-9 w-full border border-[#a85b4a] text-sm text-[#f0a8a0] disabled:opacity-50"
                >
                  Delete menu
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={confirmDelete}
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
    </main>
  );
}
