"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { EditInPlace } from "@/components/ui/craft";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { GroupPicker } from "@/components/security/GroupPicker";
import { ChevronRight, IconAccess, IconModels, IconViews } from "@/components/ui/icons";
import type { GroupRow, MenuNode, WindowActionRow } from "@/lib/api";
import {
  DEFAULT_ROOT_ICON,
  accessHref,
  boundAction,
  builderHref,
  designerHref,
  parentSelectOptions,
  wouldCreateCycle,
} from "@/lib/menuForm";
import { changeSummary, menuDraftChanges, menuPath } from "@/lib/menuTree";

export type MenuSavePatch = {
  name: string;
  parent_id: number | null;
  clear_parent: boolean;
  sequence: number;
  action_id: number | null;
  clear_action: boolean;
  group_ids: number[];
  clear_groups: boolean;
  /** Set only when the menu becomes top level without an icon (Odoo 19 needs one). */
  web_icon?: string;
};

type MenuDetailProps = {
  connectionId: string;
  menu: MenuNode;
  menus: MenuNode[];
  actions: WindowActionRow[];
  groups: GroupRow[];
  busy?: boolean;
  canMutate?: boolean;
  canDelete?: boolean;
  mutateBlocked?: string | null;
  deleteBlocked?: string | null;
  /** Controlled parent ("" = top level). Lets a drag in the tree stage a new parent here. */
  parentValue?: string;
  onParentChange?: (value: string) => void;
  onSave: (patch: MenuSavePatch) => void;
  onCreateAndBind: (opts: { name: string; model: string; view_mode: string }) => void;
  onDelete: () => void;
};

export function MenuDetail({
  connectionId,
  menu,
  menus,
  actions,
  groups,
  busy,
  canMutate = true,
  canDelete = true,
  mutateBlocked,
  deleteBlocked,
  parentValue,
  onParentChange,
  onSave,
  onCreateAndBind,
  onDelete,
}: MenuDetailProps) {
  const bound = boundAction(actions, menu.action_id);
  const originalParent = menu.parent_id != null ? String(menu.parent_id) : "";
  const [name, setName] = useState(menu.name);
  const [localParent, setLocalParent] = useState(originalParent);
  const [sequence, setSequence] = useState(menu.sequence);
  const [actionId, setActionId] = useState(menu.action_id != null ? String(menu.action_id) : "");
  const [groupIds, setGroupIds] = useState(menu.group_ids ?? []);
  const [newActionName, setNewActionName] = useState(menu.name);
  const [newActionModel, setNewActionModel] = useState(bound?.res_model ?? "");
  const [newActionMode, setNewActionMode] = useState(bound?.view_mode ?? "list,form");

  const parentId = parentValue ?? localParent;
  const setParentId = (value: string) => {
    setLocalParent(value);
    onParentChange?.(value);
  };

  const parentNum = parentId ? Number(parentId) : null;
  const cycle = wouldCreateCycle(menus, menu.id, parentNum);
  const changes = menuDraftChanges(menu, {
    name,
    parentId: parentNum,
    sequence,
    actionId: actionId ? Number(actionId) : null,
    groupIds,
  });
  const dirty = changes.length > 0;
  const movedParent = changes.includes("parent");
  const becomesRootWithoutIcon = movedParent && parentNum == null && !menu.web_icon;
  const fromName = menu.parent_id != null ? (menus.find((m) => m.id === menu.parent_id)?.name ?? `#${menu.parent_id}`) : "Top level";
  const toName = parentNum != null ? (menus.find((m) => m.id === parentNum)?.name ?? `#${parentNum}`) : "Top level";
  const path = menuPath(menus, menu.id).slice(0, -1);
  const model = bound?.res_model || newActionModel.trim();
  const saveDisabled = busy || !dirty || !name.trim() || cycle || !canMutate;

  function discard() {
    setName(menu.name);
    setParentId(originalParent);
    setSequence(menu.sequence);
    setActionId(menu.action_id != null ? String(menu.action_id) : "");
    setGroupIds(menu.group_ids ?? []);
  }

  function save() {
    onSave({
      name: name.trim(),
      parent_id: parentNum,
      clear_parent: !parentId,
      sequence,
      action_id: actionId ? Number(actionId) : null,
      clear_action: !actionId,
      group_ids: groupIds,
      clear_groups: groupIds.length === 0,
      ...(becomesRootWithoutIcon ? { web_icon: DEFAULT_ROOT_ICON } : {}),
    });
  }

  return (
    <div className="grid gap-4" data-testid="menus-detail">
      <section className="mn-panel" aria-labelledby="menus-detail-title">
        <header className="mn-panel-head">
          <div className="min-w-0">
            {path.length > 0 ? (
              <ol className="mn-crumbs" aria-label="Menu path" data-testid="menus-detail-path">
                {path.map((p, i) => (
                  <li key={`${p}-${i}`}>{p}</li>
                ))}
              </ol>
            ) : (
              <p className="mn-crumbs">Top-level app</p>
            )}
            <h2 className="mn-panel-title" id="menus-detail-title">
              {/* Touch 47: rename here; it only changes the draft name below, saved through the usual check. */}
              <EditInPlace value={name} label="Menu name" onSave={setName} />
            </h2>
            <p className="mn-panel-sub">
              Menu #{menu.id}.{" "}
              {bound?.res_model
                ? `Opens ${bound.res_model} through action #${bound.id}.`
                : menu.action_id
                  ? `Bound to action #${menu.action_id}.`
                  : "Opens nothing yet. Bind a window action below."}
            </p>
          </div>
          {model ? (
            <div className="mn-panel-links">
              <Button type="button" variant="ghost" size="sm" asChild>
                <Link href={designerHref(connectionId, model)} data-testid="menus-detail-designer">
                  <IconViews className="h-3.5 w-3.5" aria-hidden />
                  View Designer
                </Link>
              </Button>
              <Button type="button" variant="ghost" size="sm" asChild>
                <Link href={builderHref(connectionId, model)} data-testid="menus-detail-builder">
                  <IconModels className="h-3.5 w-3.5" aria-hidden />
                  Fields
                </Link>
              </Button>
              <Button type="button" variant="ghost" size="sm" asChild>
                <Link href={accessHref(connectionId, model)} data-testid="menus-detail-access">
                  <IconAccess className="h-3.5 w-3.5" aria-hidden />
                  Access
                </Link>
              </Button>
            </div>
          ) : null}
        </header>

        <fieldset className="mn-section">
          <legend className="mn-section-title">Placement</legend>
          {movedParent && !cycle ? (
            <p className="mn-moved" data-testid="menus-detail-moved">
              <span>
                Moving from <strong>{fromName}</strong> to <strong>{toName}</strong>. Not saved yet.
              </span>
              {becomesRootWithoutIcon ? (
                <span>It gets the default icon path, because Odoo 19 needs one on top-level menus.</span>
              ) : null}
            </p>
          ) : null}
          <Input
            id="menu-detail-label"
            label="Label"
            value={name}
            onChange={(e) => setName(e.target.value)}
            error={!name.trim() ? "Enter a label. Odoo shows it in the navbar." : undefined}
            aria-invalid={!name.trim() || undefined}
          />
          <div className="mn-grid-2">
            <Select
              id="menu-detail-parent"
              label="Parent"
              options={parentSelectOptions(menus, menu.id)}
              value={parentId}
              onChange={(e) => setParentId(e.target.value)}
              error={cycle ? "A menu can't sit under itself or one of its children." : undefined}
              aria-invalid={cycle || undefined}
              data-testid="menus-detail-parent"
            />
            <Input
              id="menu-detail-sequence"
              label="Sequence"
              type="number"
              inputMode="numeric"
              value={String(sequence)}
              onChange={(e) => setSequence(Number(e.target.value))}
            />
          </div>
        </fieldset>

        <fieldset className="mn-section">
          <legend className="mn-section-title">What it opens</legend>
          <Select
            id="menu-detail-action"
            label="Window action"
            options={[
              { value: "", label: "No action" },
              ...actions.map((a) => ({
                value: String(a.id),
                label: `#${a.id} ${a.name}${a.res_model ? ` (${a.res_model})` : ""}`,
              })),
            ]}
            value={actionId}
            onChange={(e) => setActionId(e.target.value)}
            hint="Standalone window actions only. Smart-button actions that need active_id stay in the View Designer."
          />
          <details className="mn-disclosure" data-testid="menus-detail-new-action">
            <summary>
              <ChevronRight aria-hidden />
              Create a new window action for this menu
            </summary>
            <div className="mn-disclosure-body">
              <p className="mn-quiet">
                Creates an ir.actions.act_window and points this menu at it right away. The previous
                action stays in Odoo.
              </p>
              <Input
                id="menu-detail-new-action-name"
                label="Action name"
                value={newActionName}
                onChange={(e) => setNewActionName(e.target.value)}
              />
              <div className="mn-grid-2">
                <Input
                  id="menu-detail-new-action-model"
                  label="Model"
                  value={newActionModel}
                  onChange={(e) => setNewActionModel(e.target.value)}
                  className="font-mono"
                  placeholder="res.partner…"
                  spellCheck={false}
                  autoComplete="off"
                />
                <Input
                  id="menu-detail-new-action-mode"
                  label="View mode"
                  value={newActionMode}
                  onChange={(e) => setNewActionMode(e.target.value)}
                  className="font-mono"
                  spellCheck={false}
                  autoComplete="off"
                />
              </div>
              <div>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={busy || !newActionName.trim() || !newActionModel.trim() || !canMutate}
                  title={mutateBlocked ?? undefined}
                  onClick={() =>
                    onCreateAndBind({
                      name: newActionName.trim(),
                      model: newActionModel.trim(),
                      view_mode: newActionMode,
                    })
                  }
                  data-testid="menus-detail-create-action"
                >
                  Create and bind the action
                </Button>
              </div>
            </div>
          </details>
        </fieldset>

        <fieldset className="mn-section">
          <legend className="mn-section-title">Who sees it</legend>
          <GroupPicker
            groups={groups}
            value={groupIds}
            onChange={setGroupIds}
            label="Visibility groups"
            hint="Empty means everyone who can open the action sees it."
            noneLabel="Visible to all users"
            testId="menus-detail-groups"
          />
        </fieldset>

        <div className="mn-savebar" data-dirty={dirty ? "true" : "false"} data-testid="menus-detail-savebar">
          <div className="mn-savebar-status" aria-live="polite">
            <p className="mn-savebar-count" data-testid="menus-detail-changes">
              {changeSummary(changes)}
            </p>
            <p className="mn-savebar-detail">
              {!canMutate && mutateBlocked
                ? mutateBlocked
                : dirty
                  ? "Nothing reaches Odoo until you save. A snapshot is taken first."
                  : "Edit a field, or drag this menu in the tree to re-parent it."}
            </p>
          </div>
          <div className="mn-savebar-actions">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={busy || !dirty}
              onClick={discard}
              data-testid="menus-detail-discard"
            >
              Discard
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              disabled={saveDisabled}
              loading={busy}
              title={mutateBlocked ?? undefined}
              onClick={save}
              data-testid="menus-detail-save"
            >
              Save the menu
            </Button>
          </div>
        </div>
      </section>

      <div className="mn-danger-row">
        <p>
          <strong>Delete this menu</strong>
          Removes it from Odoo&apos;s app switcher and navbar. You type a phrase to confirm, and a
          snapshot is taken first.
        </p>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={busy || !canDelete}
          title={deleteBlocked ?? undefined}
          className="mn-danger-btn"
          onClick={onDelete}
          data-testid="menus-detail-delete"
        >
          Delete menu
        </Button>
      </div>
    </div>
  );
}
