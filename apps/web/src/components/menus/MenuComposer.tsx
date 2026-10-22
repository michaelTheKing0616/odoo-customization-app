"use client";

import { FormEvent, type ReactNode } from "react";
import { Button } from "@/components/ui/Button";
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
  /** Session chrome (Draft / Unsaved / Saved plus Discard) shown beside the submit button. */
  sessionBar?: ReactNode;
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
  sessionBar,
}: MenuComposerProps) {
  const isRoot = !form.parent_id;
  const needsModel = form.action_mode === "create" && !form.action_model.trim();

  return (
    <form
      onSubmit={onSubmit}
      className="mn-panel"
      data-testid="menus-composer"
      aria-labelledby="menus-composer-title"
    >
      <header className="mn-panel-head">
        <div className="min-w-0">
          <p className="mn-crumbs">New menu</p>
          <h2 className="mn-panel-title" id="menus-composer-title">
            Create a menu item
          </h2>
          <p className="mn-panel-sub">
            Top-level items become app tiles. Children nest under a parent. Bind a window action so
            the item opens something.
          </p>
        </div>
      </header>

      <fieldset className="mn-section">
        <legend className="mn-section-title">Placement</legend>
        <Input
          id="menu-new-label"
          label="Label"
          required
          value={form.name}
          onChange={(e) => onChange({ name: e.target.value })}
          placeholder="Visitor log…"
          hint="Shown in Odoo's app switcher or navbar."
        />
        <div className="mn-grid-2">
          <Select
            id="menu-new-parent"
            label="Parent"
            options={parentSelectOptions(menus)}
            value={form.parent_id}
            onChange={(e) => onChange({ parent_id: e.target.value })}
            hint="Root app makes it a top-level tile."
          />
          <Input
            id="menu-new-sequence"
            label="Sequence"
            type="number"
            inputMode="numeric"
            value={String(form.sequence)}
            onChange={(e) => onChange({ sequence: Number(e.target.value) })}
            hint="Lower comes first."
          />
        </div>
        {isRoot ? (
          <Input
            id="menu-new-icon"
            label="App icon path"
            value={form.web_icon}
            onChange={(e) => onChange({ web_icon: e.target.value })}
            className="font-mono"
            spellCheck={false}
            autoComplete="off"
            hint="Odoo 19 needs a module file path such as base,static/description/icon.png. It rejects fa-* icon names."
          />
        ) : null}
      </fieldset>

      <fieldset className="mn-section">
        <legend className="mn-section-title">What it opens</legend>
        <div className="mn-seg" role="radiogroup" aria-label="Window action source">
          <label>
            <input
              type="radio"
              name="menu-action-mode"
              value="existing"
              checked={form.action_mode === "existing"}
              onChange={() => onChange({ action_mode: "existing" })}
              data-testid="menus-action-mode-existing"
            />
            Use an existing action
          </label>
          <label>
            <input
              type="radio"
              name="menu-action-mode"
              value="create"
              checked={form.action_mode === "create"}
              onChange={() => onChange({ action_mode: "create" })}
              data-testid="menus-action-mode-create"
            />
            Create a new action
          </label>
        </div>
        {form.action_mode === "existing" ? (
          <Select
            id="menu-new-action"
            label="Window action"
            options={[
              { value: "", label: "No action yet" },
              ...actions.map((a) => ({
                value: String(a.id),
                label: `#${a.id} ${a.name}${a.res_model ? ` (${a.res_model})` : ""}`,
              })),
            ]}
            value={form.action_id}
            onChange={(e) => onChange({ action_id: e.target.value })}
            hint="Standalone window actions only. Smart-button actions that need active_id stay in the View Designer."
          />
        ) : (
          <>
            <Input
              id="menu-new-action-name"
              label="Action name"
              value={form.action_name}
              onChange={(e) => onChange({ action_name: e.target.value })}
              placeholder={form.name ? `${form.name} list` : "Open records…"}
              hint="Left empty, it becomes the label plus “list”."
            />
            <div className="mn-grid-2">
              <Input
                id="menu-new-action-model"
                label="Model"
                required
                value={form.action_model}
                onChange={(e) => onChange({ action_model: e.target.value })}
                className="font-mono"
                placeholder="x_visitor_log…"
                spellCheck={false}
                autoComplete="off"
                hint="Technical name of the model this menu opens."
              />
              <Input
                id="menu-new-action-mode"
                label="View mode"
                value={form.action_view_mode}
                onChange={(e) => onChange({ action_view_mode: e.target.value })}
                className="font-mono"
                spellCheck={false}
                autoComplete="off"
              />
            </div>
          </>
        )}
      </fieldset>

      <fieldset className="mn-section">
        <legend className="mn-section-title">Who sees it</legend>
        <GroupPicker
          groups={groups}
          value={form.group_ids}
          onChange={(group_ids) => onChange({ group_ids })}
          label="Visibility groups"
          hint="Empty means everyone who can open the action sees it. Restrict it for a dedicated app tile."
          noneLabel="Visible to all users"
          testId="menus-composer-groups"
        />
      </fieldset>

      <div className="mn-savebar" data-testid="menus-composer-savebar">
        <div className="mn-savebar-status">
          {sessionBar}
          {!canSubmit && submitBlockedReason ? (
            <p className="mn-savebar-detail" data-testid="menus-create-blocked">
              {submitBlockedReason}
            </p>
          ) : needsModel ? (
            <p className="mn-savebar-detail">Add the model the new action opens.</p>
          ) : null}
        </div>
        <div className="mn-savebar-actions">
          <Button
            type="submit"
            variant="primary"
            size="sm"
            disabled={busy || !canSubmit || !form.name.trim() || needsModel}
            title={submitBlockedReason ?? undefined}
            loading={busy}
            data-testid="menus-create"
          >
            Create menu
          </Button>
        </div>
      </div>
    </form>
  );
}
