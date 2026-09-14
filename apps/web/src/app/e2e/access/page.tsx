"use client";

import { useState } from "react";
import { AccessComposer } from "@/components/access/AccessComposer";
import { AccessRightsList } from "@/components/access/AccessRightsList";
import { AccessSessionBar } from "@/components/access/AccessSessionBar";
import { RecordRulesList } from "@/components/access/RecordRulesList";
import { Callout } from "@/components/ui/Callout";
import { PageHeader } from "@/components/ui/layout-primitives";
import type { AccessRightRow, GroupRow, RecordRuleRow } from "@/lib/api";
import { defaultAccessForm } from "@/lib/accessForm";

const GROUPS: GroupRow[] = [
  { id: 1, name: "Internal User", full_name: "User types / Internal User", share: false },
];

const RIGHTS: AccessRightRow[] = [
  {
    id: 7,
    name: "Visitor log user",
    model: "x_visitor_log",
    model_id: 11,
    group_id: 1,
    group_name: "Internal User",
    perm_read: true,
    perm_write: true,
    perm_create: true,
    perm_unlink: false,
    active: true,
  },
];

const RULES: RecordRuleRow[] = [
  {
    id: 3,
    name: "Own visitor rows",
    model: "x_visitor_log",
    model_id: 11,
    domain_force: "[('create_uid', '=', user.id)]",
    group_ids: [1],
    perm_read: true,
    perm_write: true,
    perm_create: true,
    perm_unlink: true,
    active: true,
    global: false,
  },
];

export default function AccessE2ePage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const [selectedId, setSelectedId] = useState<number | null>(7);
  const [query, setQuery] = useState("");

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return (
    <main className="mx-auto max-w-6xl p-6" data-testid="access-harness">
      <PageHeader
        title="Access"
        description="E2E mock · Access lines grant CRUD. Record rules filter which rows a group can see or change."
      />
      <Callout variant="warning" title="Global grants affect every user">
        Empty groups create a global rule. Confirm before you delete. Completeness ≠ Cert ≠ Autopilot.
        Promote stays human.
      </Callout>
      <div className="mt-4 grid gap-6 lg:grid-cols-[minmax(240px,360px)_minmax(0,1fr)]">
        <div className="space-y-6">
          <AccessRightsList
            rows={RIGHTS}
            selectedId={selectedId}
            query={query}
            onQueryChange={setQuery}
            onSelect={(row) => setSelectedId(row.id)}
            onCreate={() => setSelectedId(null)}
          />
          <RecordRulesList
            rows={RULES}
            selectedId={null}
            query=""
            onQueryChange={() => undefined}
            onSelect={() => undefined}
            onCreate={() => undefined}
          />
        </div>
        <div className="space-y-4">
          <AccessSessionBar
            sessionState={selectedId ? "saved" : "draft"}
            submitLabel={selectedId ? "Saved on Odoo" : "Create access"}
            canDiscard={!selectedId}
            onDiscard={() => undefined}
          />
          <AccessComposer
            model="x_visitor_log"
            form={{
              ...defaultAccessForm(),
              name: "Visitor log user",
              group_id: "1",
            }}
            groups={GROUPS}
            onChange={() => undefined}
            onSubmit={(event) => event.preventDefault()}
          />
        </div>
      </div>
    </main>
  );
}
