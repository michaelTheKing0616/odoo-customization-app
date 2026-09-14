"use client";

import { useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { GroupPicker } from "@/components/security/GroupPicker";
import { IconAccess, IconModels, IconViews } from "@/components/ui/icons";
import type { GroupRow, MenuNode, WindowActionRow } from "@/lib/api";
import {
  accessHref,
  boundAction,
  builderHref,
  designerHref,
  parentSelectOptions,
  wouldCreateCycle,
} from "@/lib/menuForm";

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
  onSave: (patch: {
    name: string;
    parent_id: number | null;
    clear_parent: boolean;
    sequence: number;
    action_id: number | null;
    clear_action: boolean;
    group_ids: number[];
    clear_groups: boolean;
  }) => void;
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
  onSave,
  onCreateAndBind,
  onDelete,
}: MenuDetailProps) {
  const bound = boundAction(actions, menu.action_id);
  const [name, setName] = useState(menu.name);
  const [parentId, setParentId] = useState(menu.parent_id != null ? String(menu.parent_id) : "");
  const [sequence, setSequence] = useState(menu.sequence);
  const [actionId, setActionId] = useState(menu.action_id != null ? String(menu.action_id) : "");
  const [groupIds, setGroupIds] = useState(menu.group_ids ?? []);
  const [newActionName, setNewActionName] = useState(menu.name);
  const [newActionModel, setNewActionModel] = useState(bound?.res_model ?? "");
  const [newActionMode, setNewActionMode] = useState(bound?.view_mode ?? "list,form");

  const parentNum = parentId ? Number(parentId) : null;
  const cycle = wouldCreateCycle(menus, menu.id, parentNum);
  const dirty =
    name.trim() !== menu.name ||
    (parentNum ?? null) !== (menu.parent_id ?? null) ||
    sequence !== menu.sequence ||
    (actionId ? Number(actionId) : null) !== (menu.action_id ?? null) ||
    JSON.stringify([...groupIds].sort()) !== JSON.stringify([...(menu.group_ids ?? [])].sort());

  const model = bound?.res_model || newActionModel.trim();

  return (
    <div className="space-y-4" data-testid="menus-detail">
      <Card className="space-y-4 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
              Existing menu
            </p>
            <h2 className="text-base font-semibold text-ink">{menu.name}</h2>
            <p className="mt-0.5 font-mono text-[11px] text-muted">#{menu.id}</p>
          </div>
          <Badge variant={menu.action_id ? "info" : "default"}>
            {menu.action_id ? `Action ${menu.action_id}` : "No action"}
          </Badge>
        </div>
        <Input label="Label" value={name} onChange={(e) => setName(e.target.value)} />
        <Select
          label="Parent"
          options={parentSelectOptions(menus, menu.id)}
          value={parentId}
          onChange={(e) => setParentId(e.target.value)}
          error={cycle ? "A menu cannot nest under itself or a child." : undefined}
        />
        <Input
          label="Sequence"
          type="number"
          value={String(sequence)}
          onChange={(e) => setSequence(Number(e.target.value))}
        />
        <Select
          label="Bound action"
          options={[
            { value: "", label: "No action" },
            ...actions.map((a) => ({
              value: String(a.id),
              label: `#${a.id} ${a.name}${a.res_model ? ` (${a.res_model})` : ""}`,
            })),
          ]}
          value={actionId}
          onChange={(e) => setActionId(e.target.value)}
        />
        <GroupPicker
          groups={groups}
          value={groupIds}
          onChange={setGroupIds}
          label="Visibility groups"
          hint="Empty means visible to all users who can open the action."
          noneLabel="Visible to all users"
        />
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="primary"
            size="sm"
            disabled={busy || !dirty || !name.trim() || cycle || !canMutate}
            title={mutateBlocked ?? undefined}
            onClick={() =>
              onSave({
                name: name.trim(),
                parent_id: parentNum,
                clear_parent: !parentId,
                sequence,
                action_id: actionId ? Number(actionId) : null,
                clear_action: !actionId,
                group_ids: groupIds,
                clear_groups: groupIds.length === 0,
              })
            }
            data-testid="menus-detail-save"
          >
            Save menu
          </Button>
          {model ? (
            <>
              <Button type="button" variant="secondary" size="sm" asChild>
                <Link href={designerHref(connectionId, model)} data-testid="menus-detail-designer">
                  <IconViews className="h-3.5 w-3.5" aria-hidden />
                  View Designer
                </Link>
              </Button>
              <Button type="button" variant="secondary" size="sm" asChild>
                <Link href={builderHref(connectionId, model)} data-testid="menus-detail-builder">
                  <IconModels className="h-3.5 w-3.5" aria-hidden />
                  Models and fields
                </Link>
              </Button>
              <Button type="button" variant="secondary" size="sm" asChild>
                <Link href={accessHref(connectionId, model)} data-testid="menus-detail-access">
                  <IconAccess className="h-3.5 w-3.5" aria-hidden />
                  Access
                </Link>
              </Button>
            </>
          ) : null}
        </div>
      </Card>

      <Card className="space-y-3 p-5">
        <div>
          <h3 className="text-sm font-semibold text-ink">Create and bind an action</h3>
          <p className="mt-1 text-xs text-muted">
            Creates ir.actions.act_window and points this menu at it. Does not rewrite the previous
            action.
          </p>
        </div>
        <Input
          label="Action name"
          value={newActionName}
          onChange={(e) => setNewActionName(e.target.value)}
        />
        <Input
          label="Model"
          value={newActionModel}
          onChange={(e) => setNewActionModel(e.target.value)}
          className="font-mono"
          placeholder="res.partner"
        />
        <Input
          label="View mode"
          value={newActionMode}
          onChange={(e) => setNewActionMode(e.target.value)}
          className="font-mono"
        />
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
          Create action and bind
        </Button>
      </Card>

      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={busy || !canDelete}
        title={deleteBlocked ?? undefined}
        className="text-danger"
        onClick={onDelete}
        data-testid="menus-detail-delete"
      >
        Delete menu
      </Button>
    </div>
  );
}
