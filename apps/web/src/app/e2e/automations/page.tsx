"use client";

import { useState } from "react";
import { AutomationComposer } from "@/components/automations/AutomationComposer";
import { AutomationDetail } from "@/components/automations/AutomationDetail";
import { AutomationSessionBar } from "@/components/automations/AutomationSessionBar";
import { AutomationsList } from "@/components/automations/AutomationsList";
import { Callout } from "@/components/ui/Callout";
import { PageHeader } from "@/components/ui/layout-primitives";
import type { AutomationRow, Connection, ModelRow } from "@/lib/api";
import { defaultComposerForm } from "@/lib/automationForm";

const CONNECTION: Connection = {
  id: "e2e-mock",
  name: "E2E mock",
  url: "http://127.0.0.1:8069",
  db_name: "odoo_dev",
  username: "admin",
  server_version: "19.0",
  write_mode: "standard",
  created_at: null,
  updated_at: null,
  capabilities: {
    major: 19,
    edition: "community",
    server_version: "19.0",
    ga: true,
    message: "ok",
    supported: [
      "base_automation_safe_triggers",
      "object_write_update_path",
      "related_write_dotted_path",
      "object_create_crud_model",
    ],
    unsupported: [],
  },
};

const MODELS: ModelRow[] = [
  { id: 1, model: "x_visitor_log", name: "Visitor log", state: "manual", transient: false },
];

const ROWS: AutomationRow[] = [
  {
    id: 42,
    name: "Set checked-in on create",
    model: "x_visitor_log",
    model_id: 1,
    trigger: "on_create",
    active: true,
    filter_domain: "[('x_host_id', '!=', False)]",
    action_server_ids: [9],
  },
];

export default function AutomationsE2ePage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const [selectedId, setSelectedId] = useState<number | null>(42);
  const [query, setQuery] = useState("");
  const selected = ROWS.find((row) => row.id === selectedId) ?? null;

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return (
    <main className="mx-auto max-w-6xl p-6" data-testid="automations-harness">
      <PageHeader
        title="Automations"
        description="E2E mock · Model, trigger, apply-on, then a safe action. Python stays Option A unless you confirm live code."
      />
      <Callout variant="info" title="Sandbox first">
        Form buttons live in View Designer. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
      </Callout>
      <div className="mt-4 grid gap-6 lg:grid-cols-[minmax(240px,320px)_minmax(0,1fr)]">
        <AutomationsList
          rows={ROWS}
          selectedId={selectedId}
          modelFilter=""
          query={query}
          onQueryChange={setQuery}
          onSelect={(row) => setSelectedId(row.id)}
          onCreate={() => setSelectedId(null)}
        />
        <div className="space-y-4">
          {selected ? (
            <AutomationDetail
              connectionId="e2e-mock"
              row={selected}
              onSave={() => undefined}
              onDuplicate={() => setSelectedId(null)}
              onToggleActive={() => undefined}
              onDelete={() => undefined}
            />
          ) : (
            <>
              <AutomationSessionBar
                sessionState="draft"
                submitLabel="Create automation"
                canDiscard={false}
                onDiscard={() => undefined}
              />
              <AutomationComposer
                connectionId="e2e-mock"
                connection={CONNECTION}
                form={{
                  ...defaultComposerForm("x_visitor_log"),
                  name: "Mark host notified",
                  field_name: "x_notified",
                  value: "true",
                }}
                onChange={() => undefined}
                onSubmit={(event) => event.preventDefault()}
                busy={false}
                canSubmit
                supportedTriggers={new Set(["on_create", "on_write", "on_create_or_write"])}
                activityTypes={[]}
                mailTemplates={[]}
                models={MODELS}
              />
            </>
          )}
        </div>
      </div>
    </main>
  );
}
