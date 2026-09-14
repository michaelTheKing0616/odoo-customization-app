"use client";

import { useState } from "react";
import { BuilderModelsList } from "@/components/builder/BuilderModelsList";
import { BuilderSessionBar } from "@/components/builder/BuilderSessionBar";
import { ModelComposer } from "@/components/builder/ModelComposer";
import { ModelDetail } from "@/components/builder/ModelDetail";
import { Callout } from "@/components/ui/Callout";
import { PageHeader } from "@/components/ui/layout-primitives";
import type { FieldRow, ModelRow } from "@/lib/api";
import { defaultModelForm } from "@/lib/builderForm";

const MODELS: ModelRow[] = [
  { id: 11, model: "x_visitor_log", name: "Visitor log", state: "manual", transient: false },
];

const FIELDS: FieldRow[] = [
  {
    id: 101,
    name: "x_name",
    field_description: "Guest",
    ttype: "char",
    required: true,
    readonly: false,
    relation: null,
    state: "manual",
  },
  {
    id: 102,
    name: "x_host_id",
    field_description: "Host",
    ttype: "many2one",
    required: false,
    readonly: false,
    relation: "res.users",
    state: "manual",
  },
];

export default function BuilderE2ePage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const [selectedModel, setSelectedModel] = useState<string | null>("x_visitor_log");
  const [query, setQuery] = useState("");
  const selected = MODELS.find((row) => row.model === selectedModel) ?? null;

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return (
    <main className="mx-auto max-w-6xl p-6" data-testid="builder-harness">
      <PageHeader
        title="Models & Fields"
        description="E2E mock · Create an x_ model, add fields, then jump to View Designer. Prefer a sandbox before production writes."
      />
      <Callout variant="info" title="Hide in view ≠ remove from model">
        Hiding a field is a View Designer change. Removing it here drops the column. Completeness ≠
        Cert ≠ Autopilot. Promote stays human.
      </Callout>
      <div className="mt-4 grid gap-6 lg:grid-cols-[minmax(240px,320px)_minmax(0,1fr)]">
        <BuilderModelsList
          rows={MODELS}
          selectedModel={selectedModel}
          query={query}
          onQueryChange={setQuery}
          onSelect={(row) => setSelectedModel(row.model)}
          onCreate={() => setSelectedModel(null)}
          onOpenExisting={(model) => setSelectedModel(model)}
        />
        <div className="space-y-4">
          {selected ? (
            <ModelDetail
              connectionId="e2e-mock"
              model={selected.model}
              modelLabel={selected.name}
              customRow={selected}
              fields={FIELDS}
              fieldQuery=""
              selectedFieldId={101}
              justCreated
              onFieldQueryChange={() => undefined}
              onSelectField={() => undefined}
              onNewField={() => undefined}
              onRemoveField={() => undefined}
            />
          ) : (
            <>
              <BuilderSessionBar
                sessionState="draft"
                submitLabel="Create model"
                canDiscard={false}
                onDiscard={() => undefined}
              />
              <ModelComposer
                form={{ ...defaultModelForm(), name: "Visitor log", model: "x_visitor_log" }}
                onChange={() => undefined}
                onSubmit={(event) => event.preventDefault()}
              />
            </>
          )}
        </div>
      </div>
    </main>
  );
}
