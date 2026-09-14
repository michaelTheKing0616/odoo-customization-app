"use client";

import { FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { GroupPicker } from "@/components/security/GroupPicker";
import type { GroupRow, MenuNode, WindowActionRow } from "@/lib/api";
import { parentSelectOptions, type MenuComposerForm } from "@/lib/menuForm";

type MenuComposerProps = {
  form: MenuComposerForm;
  menus: MenuNode[];
  actions: WindowActionRow[];
  groups: GroupRow[];
  onChange: (patch: Partial<MenuComposerForm>) => void;
  onSubmit: (e: FormEvent) => void;
  busy?: boolean;
  canSubmit?: boolean;
  submitBlockedReason?: string | null;
};

export function MenuComposer({
  form,
  menus,
  actions,
  groups,
  onChange,
  onSubmit,
  busy,
  canSubmit = true,
  submitBlockedReason,
}: MenuComposerProps) {
  const isRoot = !form.parent_id;

  return (
    <form onSubmit={onSubmit} className="space-y-4" data-testid="menus-composer">
      <Card className="space-y-4 p-5">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">New menu</p>
          <h2 className="text-base font-semibold text-ink">Create a menu item</h2>
          <p className="mt-1 text-sm text-muted">
            Root items become app tiles. Children nest under a parent. Bind a window action so
            Open-in-Odoo has somewhere to go.
          </p>
        </div>
        <Input
          label="Label"
          required
          value={form.name}
          onChange={(e) => onChange({ name: e.target.value })}
          placeholder="Visitor log"
          hint="Shown in the Odoo app switcher or navbar."
        />
        <Select
          label="Parent"
          options={parentSelectOptions(menus)}
          value={form.parent_id}
          onChange={(e) => onChange({ parent_id: e.target.value })}
          hint="Empty parent creates a root app menu."
        />
        <Input
          label="Sequence"
          type="number"
          value={String(form.sequence)}
          onChange={(e) => onChange({ sequence: Number(e.target.value) })}
          hint="Lower numbers appear first among siblings."
        />
        {isRoot ? (
          <Input
            label="Root icon"
            value={form.web_icon}
            onChange={(e) => onChange({ web_icon: e.target.value })}
            className="font-mono"
            hint="Odoo 19 needs a module file path. Font Awesome fa-* strings are rejected."
          />
        ) : null}

        <fieldset className="space-y-3 rounded-md border border-border-subtle p-3">
          <legend className="px-1 text-sm font-medium text-ink">Window action</legend>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant={form.action_mode === "existing" ? "primary" : "secondary"}
              onClick={() => onChange({ action_mode: "existing" })}
            >
              Bind existing
            </Button>
            <Button
              type="button"
              size="sm"
              variant={form.action_mode === "create" ? "primary" : "secondary"}
              onClick={() => onChange({ action_mode: "create" })}
            >
              Create action
            </Button>
          </div>
          {form.action_mode === "existing" ? (
            <Select
              label="Action"
              options={[
                { value: "", label: "No action yet" },
                ...actions.map((a) => ({
                  value: String(a.id),
                  label: `#${a.id} ${a.name}${a.res_model ? ` (${a.res_model})` : ""}`,
                })),
              ]}
              value={form.action_id}
              onChange={(e) => onChange({ action_id: e.target.value })}
              hint="Standalone window actions first. Related-button actions that need active_id stay off the menu."
            />
          ) : (
            <div className="space-y-3">
              <Input
                label="Action name"
                required
                value={form.action_name}
                onChange={(e) => onChange({ action_name: e.target.value })}
                placeholder={form.name ? `${form.name} list` : "Open records"}
              />
              <Input
                label="Model"
                required
                value={form.action_model}
                onChange={(e) => onChange({ action_model: e.target.value })}
                className="font-mono"
                placeholder="x_visitor_log"
                hint="Technical model this menu opens."
              />
              <Input
                label="View mode"
                value={form.action_view_mode}
                onChange={(e) => onChange({ action_view_mode: e.target.value })}
                className="font-mono"
              />
            </div>
          )}
        </fieldset>

        <GroupPicker
          groups={groups}
          value={form.group_ids}
          onChange={(group_ids) => onChange({ group_ids })}
          label="Visibility groups"
          hint="Empty means every user who can reach the bound action. Restrict when this is a dedicated app tile."
          noneLabel="Visible to all users"
        />

        <Button
          type="submit"
          variant="primary"
          disabled={busy || !canSubmit || !form.name.trim()}
          title={submitBlockedReason ?? undefined}
          loading={busy}
          data-testid="menus-create"
        >
          Create menu
        </Button>
      </Card>
    </form>
  );
}
