"use client";

import { useState } from "react";
import { MenuComposer } from "@/components/menus/MenuComposer";
import { MenuSessionBar } from "@/components/menus/MenuSessionBar";
import { MenusTree } from "@/components/menus/MenusTree";
import { Callout } from "@/components/ui/Callout";
import { PageHeader } from "@/components/ui/layout-primitives";
import type { MenuNode, WindowActionRow } from "@/lib/api";
import { defaultMenuForm } from "@/lib/menuForm";

const MENUS: MenuNode[] = [
  {
    id: 1,
    name: "Visitor log",
    parent_id: null,
    action: "ir.actions.act_window,10",
    action_id: 10,
    sequence: 10,
    web_icon: "base,static/description/icon.png",
    child_count: 1,
    group_ids: [],
  },
  {
    id: 2,
    name: "Checked in",
    parent_id: 1,
    parent_name: "Visitor log",
    action: "ir.actions.act_window,11",
    action_id: 11,
    sequence: 5,
    web_icon: null,
    child_count: 0,
    group_ids: [],
  },
];

const ACTIONS: WindowActionRow[] = [
  {
    id: 10,
    name: "Visitor log",
    res_model: "x_visitor_log",
    view_mode: "list,form",
  },
];

export default function MenusE2ePage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const [selectedId, setSelectedId] = useState<number | null>(1);
  const [query, setQuery] = useState("");

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return (
    <main className="mx-auto max-w-6xl p-6" data-testid="menus-harness">
      <PageHeader
        title="Menus"
        description="E2E mock · Root menus need a file-path icon on Odoo 19. Bind a standalone window action."
      />
      <Callout variant="info" title="Related-button actions stay off this tree">
        Actions that need active_id are Designer smart buttons, not app menus. Completeness ≠ Cert ≠
        Autopilot. Promote stays human.
      </Callout>
      <div className="mt-4 grid gap-6 lg:grid-cols-[minmax(240px,320px)_minmax(0,1fr)]">
        <MenusTree
          menus={MENUS}
          selectedId={selectedId}
          query={query}
          onQueryChange={setQuery}
          onSelect={(menu) => setSelectedId(menu.id)}
          onCreate={() => setSelectedId(null)}
        />
        <div className="space-y-4">
          <MenuSessionBar
            sessionState={selectedId ? "saved" : "draft"}
            submitLabel={selectedId ? "Saved on Odoo" : "Create menu"}
            canDiscard={!selectedId}
            onDiscard={() => undefined}
          />
          <MenuComposer
            form={{
              ...defaultMenuForm(),
              name: selectedId ? "Visitor log" : "Front desk",
              web_icon: "base,static/description/icon.png",
              action_id: "10",
            }}
            menus={MENUS}
            actions={ACTIONS}
            groups={[]}
            onChange={() => undefined}
            onSubmit={(event) => event.preventDefault()}
          />
        </div>
      </div>
    </main>
  );
}
