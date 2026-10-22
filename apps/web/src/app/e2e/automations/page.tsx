"use client";

import { Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AutomationComposer } from "@/components/automations/AutomationComposer";
import { AutomationDetail } from "@/components/automations/AutomationDetail";
import { AutomationSessionBar } from "@/components/automations/AutomationSessionBar";
import { AutomationsList } from "@/components/automations/AutomationsList";
import { AutomationsStateGuide } from "@/components/automations/AutomationsStateGuide";
import { GatingCallout } from "@/components/GatingCallout";
import { OperateStudioChrome } from "@/components/operate-studio/OperateStudioChrome";
import type {
  AutomationRow,
  AutomationsGateResponse,
  Connection,
  GatingChoiceId,
  ModelRow,
} from "@/lib/api";
import {
  LIBRARY_FINE_SNIPPET,
  defaultComposerForm,
} from "@/lib/automationForm";
import "@/components/automations/automations-operate.css";

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

const GATED: AutomationsGateResponse = {
  automations: {
    feature: "automations",
    title: "Automations aren't available on this connection",
    why: "Automation rules need the base_automation module, which isn't installed on this Odoo Online instance (it ships with Odoo's Custom plan).",
    options: [
      "Upgrade the Odoo subscription to the Custom plan to unlock live automations.",
      "Deploying to Odoo.sh or self-hosted? Export this as a module with scheduled actions instead.",
      "Or leave automations out — everything else here works fully.",
    ],
    available: false,
    capability_key: "base_automation",
    gating_choices: [
      { id: "upgrade_plan", label: "Upgrade the Odoo subscription to the Custom plan" },
      { id: "export_module", label: "Export as a module with scheduled actions instead" },
      { id: "leave_out", label: "Leave automations out" },
    ],
  },
  approvals: {
    feature: "approval_rules",
    title: "Approval rules aren't available on this connection",
    why: "Approval rules are Enterprise-only and were not detected on this database.",
    options: [],
    available: false,
    capability_key: "approval_rules_studio",
    gating_choices: [],
  },
};

function connectionFor(state: string): Connection {
  const online = state === "online" || state === "gate";
  return {
    id: "e2e-mock",
    name: online ? "E2E Online" : "E2E mock",
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
      hosting_hint: online ? "online" : "self_hosted",
      python_module_install: !online,
      supported: [
        "base_automation_safe_triggers",
        "object_write_update_path",
        "related_write_dotted_path",
        "object_create_crud_model",
      ],
      unsupported: [],
    },
  };
}

function AutomationsE2eInner() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const searchParams = useSearchParams();
  const state = searchParams.get("state") || "detail";
  const connection = useMemo(() => connectionFor(state), [state]);
  const [selectedId, setSelectedId] = useState<number | null>(
    state === "detail" ? 42 : null,
  );
  const [query, setQuery] = useState("");
  const [gatingChoice, setGatingChoice] = useState<GatingChoiceId | null>(null);
  const rows = state === "empty" ? [] : ROWS;
  const selected = rows.find((row) => row.id === selectedId) ?? null;

  const form = useMemo(() => {
    const base = defaultComposerForm("x_visitor_log");
    if (state === "code") {
      return {
        ...base,
        name: "Library fine on return",
        model: "x_lib_loan",
        trigger: "on_write",
        filter_domain: "[('x_returned', '=', True)]",
        action_kind: "python_module" as const,
        python_code: LIBRARY_FINE_SNIPPET,
        module_technical_name: "library_fine_on_return",
      };
    }
    if (state === "webhook") {
      return {
        ...base,
        name: "Notify external CRM",
        model: "x_visitor_log",
        trigger: "on_create",
        action_kind: "webhook" as const,
        webhook_url: "https://example.com/hooks/odoo",
        webhook_field_names: "name, email",
      };
    }
    if (state === "online") {
      return {
        ...base,
        name: "Online Option A draft",
        model: "x_visitor_log",
        trigger: "on_create",
        action_kind: "python_module" as const,
        python_code: LIBRARY_FINE_SNIPPET,
        module_technical_name: "online_option_a_demo",
      };
    }
    return {
      ...base,
      name: "Mark host notified",
      field_name: "x_notified",
      value: "true",
    };
  }, [state]);

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  const showComposer =
    state === "composer" ||
    state === "code" ||
    state === "webhook" ||
    state === "online" ||
    state === "empty" ||
    (state !== "detail" && state !== "gate" && !selected);

  return (
    <div data-testid="automations-harness-root">
    <OperateStudioChrome
      testIdPrefix="automations"
      pageTestId="automations-harness"
      kicker="E2E harness"
      title="Automations"
      subtitle="Model, trigger, apply-on, then a safe action. Python changes need a person to approve them."
      badge={{ label: "Ready", variant: "default" }}
      honesty={{
        title: "Python changes need a person to approve them.",
        why: "Completeness is not Cert and not Autopilot.",
        next: "Name the rule, pick a model and trigger, then Create.",
      }}
      shellClassName="automations-operate"
      className="p-4 sm:p-6"
    >
      <span className="sr-only" data-testid="automations-honesty">honesty</span>


      {state === "gate" ? (
        <div className="mt-6 space-y-4">
          <GatingCallout
            gating={GATED.automations}
            selectedChoice={gatingChoice}
            onSelectChoice={setGatingChoice}
          />
          <AutomationsStateGuide
            tone="warning"
            testId="automations-gate-guide"
            guide={{
              title: "Automations stay gated on this connection",
              why: "base_automation is not available on this Online plan.",
              next: "Pick a gating choice above, or export a module for Odoo.sh or self-hosted.",
            }}
          />
        </div>
      ) : (
        <div className="mt-4 grid gap-6 lg:grid-cols-[minmax(240px,320px)_minmax(0,1fr)]">
          <AutomationsList
            rows={rows}
            selectedId={selectedId}
            modelFilter=""
            query={query}
            onQueryChange={setQuery}
            onSelect={(row) => setSelectedId(row.id)}
            onCreate={() => setSelectedId(null)}
          />
          <div className="space-y-4">
            {selected && state === "detail" ? (
              <AutomationDetail
                connectionId="e2e-mock"
                row={selected}
                onSave={() => undefined}
                onDuplicate={() => setSelectedId(null)}
                onToggleActive={() => undefined}
                onDelete={() => undefined}
              />
            ) : showComposer || !selected ? (
              <>
                <AutomationSessionBar
                  sessionState={state === "composer" ? "unsaved" : "draft"}
                  submitLabel={
                    state === "code" || state === "online"
                      ? "Generate module zip"
                      : state === "webhook"
                        ? "Create advanced automation"
                        : "Create automation"
                  }
                  canDiscard={state === "composer"}
                  onDiscard={() => undefined}
                />
                <AutomationComposer
                  connectionId="e2e-mock"
                  connection={connection}
                  form={form}
                  onChange={() => undefined}
                  onSubmit={(event) => event.preventDefault()}
                  busy={false}
                  canSubmit={state !== "gate"}
                  supportedTriggers={new Set(["on_create", "on_write", "on_create_or_write"])}
                  activityTypes={[]}
                  mailTemplates={[]}
                  models={MODELS}
                />
              </>
            ) : null}
          </div>
        </div>
      )}
    </OperateStudioChrome>
    </div>
  );
}

export default function AutomationsE2ePage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm text-muted">Loading harness…</main>}>
      <AutomationsE2eInner />
    </Suspense>
  );
}
