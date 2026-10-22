"use client";

import { Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { OperateStudioChrome } from "@/components/operate-studio/OperateStudioChrome";
import { ListComposerShell } from "@/components/ui/ListComposerShell";
import { MenuComposer } from "@/components/menus/MenuComposer";
import { MenuDetail } from "@/components/menus/MenuDetail";
import { MenuSessionBar } from "@/components/menus/MenuSessionBar";
import { MenuSnapshots } from "@/components/menus/MenuSnapshots";
import { MenusStateGuide } from "@/components/menus/MenusStateGuide";
import { MenusTree, type DropRefusal } from "@/components/menus/MenusTree";
import type { GroupRow, MenuNode, SnapshotRow, WindowActionRow } from "@/lib/api";
import { defaultMenuForm, wouldCreateCycle, type MenuComposerForm } from "@/lib/menuForm";
import { applyDraftParent, dropVerdict, menusErrorGuide } from "@/lib/menuTree";
import "@/components/menus/menus-operate.css";

const MENUS: MenuNode[] = [
  { id: 1, name: "Front desk", parent_id: null, action: null, action_id: null, sequence: 10, web_icon: "base,static/description/icon.png", child_count: 2, group_ids: [] },
  { id: 2, name: "Visitors", parent_id: 1, parent_name: "Front desk", action: "ir.actions.act_window,10", action_id: 10, sequence: 10, web_icon: null, child_count: 2, group_ids: [] },
  { id: 3, name: "Checked in", parent_id: 2, parent_name: "Visitors", action: "ir.actions.act_window,11", action_id: 11, sequence: 10, web_icon: null, child_count: 0, group_ids: [] },
  { id: 4, name: "Expected today", parent_id: 2, parent_name: "Visitors", action: "ir.actions.act_window,12", action_id: 12, sequence: 20, web_icon: null, child_count: 0, group_ids: [] },
  { id: 5, name: "Configuration", parent_id: 1, parent_name: "Front desk", action: null, action_id: null, sequence: 90, web_icon: null, child_count: 1, group_ids: [3] },
  { id: 6, name: "Badge types", parent_id: 5, parent_name: "Configuration", action: "ir.actions.act_window,13", action_id: 13, sequence: 10, web_icon: null, child_count: 0, group_ids: [3] },
  { id: 7, name: "Fleet", parent_id: null, action: "ir.actions.act_window,14", action_id: 14, sequence: 20, web_icon: "fleet,static/description/icon.png", child_count: 0, group_ids: [] },
];

const ACTIONS: WindowActionRow[] = [
  { id: 10, name: "Visitors", res_model: "x_visitor", view_mode: "list,form" },
  { id: 11, name: "Checked in", res_model: "x_visitor", view_mode: "list,form" },
  { id: 12, name: "Expected today", res_model: "x_visitor", view_mode: "list,form" },
  { id: 13, name: "Badge types", res_model: "x_badge_type", view_mode: "list,form" },
  { id: 14, name: "Vehicles", res_model: "fleet.vehicle", view_mode: "kanban,list,form" },
];

const GROUPS: GroupRow[] = [
  { id: 1, name: "Internal User", full_name: "User types / Internal User", share: false },
  { id: 3, name: "Administrator", full_name: "Front desk / Administrator", share: false },
];

const SNAPSHOTS: SnapshotRow[] = [
  { id: "a1b2c3d4e5f6", resource_type: "menu", resource_key: "5", label: "Menu Configuration before edit", reversible: "yes", created_at: "2026-10-05T17:40:00Z" },
  { id: "b2c3d4e5f6a1", resource_type: "action", resource_key: "13", label: "Action Badge types created", reversible: "partial", created_at: "2026-10-05T16:12:00Z" },
];

const BLOCKED_REASON = "This connection is read-only. Switch write mode to Standard on Overview to edit menus.";

type HarnessState = "default" | "new" | "staged" | "refused" | "empty" | "loading" | "error" | "blocked";

const KNOWN: HarnessState[] = ["default", "new", "staged", "refused", "empty", "loading", "error", "blocked"];

export default function MenusE2ePage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }
  return (
    <Suspense fallback={null}>
      <HarnessFromQuery />
    </Suspense>
  );
}

function HarnessFromQuery() {
  const raw = useSearchParams().get("state");
  const state = KNOWN.includes(raw as HarnessState) ? (raw as HarnessState) : "default";
  return <MenusHarness key={state} state={state} />;
}

function MenusHarness({ state }: { state: HarnessState }) {
  const [menus, setMenus] = useState<MenuNode[]>(state === "empty" ? [] : MENUS);
  const [selectedId, setSelectedId] = useState<number | null>(
    state === "new" || state === "empty" || state === "error" || state === "loading" ? null : state === "staged" ? 6 : 2,
  );
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState<{ menuId: number; value: string } | null>(
    state === "staged" ? { menuId: 6, value: "2" } : null,
  );
  const [notice, setNotice] = useState<string | null>(null);
  const [form, setForm] = useState<MenuComposerForm>(() => ({ ...defaultMenuForm(), name: state === "new" ? "Front desk" : "" }));
  const canMutate = state !== "blocked";

  const refusal = useMemo<DropRefusal | null>(() => {
    if (state !== "refused") return null;
    const v = dropVerdict(MENUS, 2, 3);
    return v.ok ? null : v;
  }, [state]);

  const staged = useMemo(() => {
    if (!draft) return null;
    const parentId = draft.value ? Number(draft.value) : null;
    return wouldCreateCycle(menus, draft.menuId, parentId) ? null : { menuId: draft.menuId, parentId };
  }, [draft, menus]);
  const treeMenus = useMemo(() => applyDraftParent(menus, staged), [menus, staged]);
  const selected = menus.find((m) => m.id === selectedId) ?? null;

  return (
    <div data-testid="menus-harness-root">
    <OperateStudioChrome
      testIdPrefix="menus"
      pageTestId="menus-harness"
      kicker="E2E harness"
      title="Menus"
      subtitle="Where each menu sits, what it opens, and who sees it."
      badge={{ label: "Ready", variant: "default" }}
      honesty={{
        title: "Tree edits stay local until Save the menu.",
        why: "Drag re-parent stages a move. Odoo refuses recursive menus before anything writes.",
        next: "Select a row, edit the detail, then Save the menu.",
      }}
      shellClassName="menus-operate"
      className="p-4 sm:p-6"
    >
      <p className="mn-intro">
        Top-level menus need an icon file path on Odoo 19. Bind a standalone window action so each
        item opens a model. Smart-button actions that need active_id stay off this tree.
      </p>
      {state === "blocked" ? (
        <Callout variant="warning" title="Changes are switched off" className="mt-4">
          {BLOCKED_REASON}
        </Callout>
      ) : null}
      {state === "error" ? (
        <MenusStateGuide
          className="mt-4"
          tone="danger"
          live
          testId="menus-error"
          guide={menusErrorGuide("load", "Odoo RPC error: Access Denied for ir.ui.menu read")}
          actions={
            <Button type="button" variant="secondary" size="sm">
              Try again
            </Button>
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
              menus={state === "error" ? [] : treeMenus}
              actions={ACTIONS}
              loading={state === "loading"}
              selectedId={selectedId}
              query={query}
              onQueryChange={setQuery}
              onSelect={(menu) => {
                setSelectedId(menu.id);
                setNotice(null);
                setDraft((d) => (d && d.menuId === menu.id ? d : null));
              }}
              onCreate={() => {
                setSelectedId(null);
                setDraft(null);
              }}
              onMove={(menu, parentId) => {
                setSelectedId(menu.id);
                setNotice(null);
                setDraft({ menuId: menu.id, value: parentId == null ? "" : String(parentId) });
              }}
              canMove={canMutate}
              moveBlockedReason={canMutate ? null : BLOCKED_REASON}
              stagedMenuId={staged?.menuId ?? null}
              defaultRefusal={refusal}
              unavailable={state === "error"}
            />
            {state === "loading" || state === "error" ? null : (
              <MenuSnapshots connectionId="demo-conn" snapshots={SNAPSHOTS} onRollback={() => undefined} />
            )}
          </>
        }
        detail={
          selected ? (
            <MenuDetail
              key={selected.id}
              connectionId="demo-conn"
              menu={selected}
              menus={menus}
              actions={ACTIONS}
              groups={GROUPS}
              canMutate={canMutate}
              canDelete={canMutate}
              mutateBlocked={canMutate ? null : BLOCKED_REASON}
              deleteBlocked={canMutate ? null : BLOCKED_REASON}
              parentValue={
                draft?.menuId === selected.id
                  ? draft.value
                  : selected.parent_id != null
                    ? String(selected.parent_id)
                    : ""
              }
              onParentChange={(value) => {
                const original = selected.parent_id != null ? String(selected.parent_id) : "";
                setDraft(value === original ? null : { menuId: selected.id, value });
              }}
              onSave={(patch) => {
                setMenus((prev) =>
                  applyDraftParent(
                    prev.map((m) =>
                      m.id === selected.id
                        ? { ...m, name: patch.name, sequence: patch.sequence, action_id: patch.action_id, group_ids: patch.group_ids }
                        : m,
                    ),
                    { menuId: selected.id, parentId: patch.parent_id },
                  ),
                );
                setDraft(null);
                setNotice(`Saved “${patch.name}” to Odoo.`);
              }}
              onCreateAndBind={() => undefined}
              onDelete={() => undefined}
            />
          ) : (
            <MenuComposer
              form={form}
              menus={menus}
              actions={ACTIONS}
              groups={GROUPS}
              onChange={(patch) => setForm((f) => ({ ...f, ...patch }))}
              onSubmit={(event) => event.preventDefault()}
              canSubmit={canMutate}
              submitBlockedReason={canMutate ? null : BLOCKED_REASON}
              sessionBar={
                <MenuSessionBar
                  className="mn-session-inline"
                  sessionState={form.name ? "unsaved" : "draft"}
                  canDiscard={Boolean(form.name)}
                  submitLabel="Create menu"
                  onDiscard={() => setForm(defaultMenuForm())}
                />
              }
            />
          )
        }
      />
    </OperateStudioChrome>
    </div>
  );
}
