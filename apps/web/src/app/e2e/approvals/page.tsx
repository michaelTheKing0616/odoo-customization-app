"use client";

import { FormEvent, Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { OperateStudioChrome } from "@/components/operate-studio/OperateStudioChrome";
import { Callout } from "@/components/ui/Callout";
import { Tabs } from "@/components/ui/Tabs";
import { ApprovalRuleComposer } from "@/components/approvals/ApprovalRuleComposer";
import { ApprovalRulesList } from "@/components/approvals/ApprovalRulesList";
import { ApprovalEntriesList } from "@/components/approvals/ApprovalEntriesList";
import { ApprovalsStateGuide } from "@/components/approvals/ApprovalsStateGuide";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import type {
  ApprovalButton,
  ApprovalEntry,
  ApprovalRule,
  ApprovalsGateResponse,
  ProcessGateResponse,
  ProcessRequestRow,
  ProcessTypeRow,
} from "@/lib/api";
import {
  INBOX_HINT,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  approvalsErrorGuide,
  defaultApprovalRuleForm,
  engineChipLabel,
  engineHint,
  processEngineLabel,
  processesEmptyGuide,
  type ApprovalRuleForm,
  type ApprovalsTab,
} from "@/lib/approvalScreen";
import "@/components/approvals/approvals-operate.css";

const GATE: ApprovalsGateResponse = {
  engine: "community",
  studio_available: false,
  studio_verify_state: "n/a",
  community_available: true,
  studio_note: null,
  gating: {
    feature: "approvals",
    title: "Odoo approval rules",
    why: "Button gating is available on Community.",
    options: ["Deploy a Community rule", "Use Studio when detected"],
    available: true,
    capability_key: "approvals",
    gating_choices: [],
  },
};

const STUDIO_GATE: ApprovalsGateResponse = {
  ...GATE,
  engine: "studio",
  studio_available: true,
  studio_verify_state: "ok",
  studio_note: "Studio approval rules detected on this database.",
};

const RULES: ApprovalRule[] = [
  {
    id: "rule-1",
    connection_id: "demo-conn",
    engine: "community",
    name: "Confirm partner",
    target_model: "res.partner",
    button_method: "action_confirm",
    button_label: "Confirm",
    steps: [{ order: 1, approver_user_ids: [2], exclusive: false }],
    active: true,
    deployed: true,
  },
  {
    id: "rule-2",
    connection_id: "demo-conn",
    engine: "community",
    name: "Validate quotation",
    target_model: "sale.order",
    button_method: "action_confirm",
    button_label: "Confirm",
    steps: [{ order: 1, approver_user_ids: [2, 3], exclusive: false }],
    active: true,
    deployed: false,
  },
];

const ENTRIES: ApprovalEntry[] = [
  {
    id: "entry-1",
    rule_id: "rule-1",
    record_model: "res.partner",
    record_id: 42,
    step_order: 1,
    status: "pending",
    approver_user_id: 2,
    message: "Waiting for manager approval before Confirm runs.",
  },
  {
    id: "entry-2",
    rule_id: "rule-1",
    record_model: "res.partner",
    record_id: 7,
    step_order: 1,
    status: "approved",
    approver_user_id: 2,
    message: "Approved by user 2.",
  },
];

const BUTTONS: ApprovalButton[] = [
  { name: "action_confirm", label: "Confirm", bulk_safe: false, reason: "header", in_header: true },
  { name: "action_cancel", label: "Cancel", bulk_safe: true, reason: "form", in_header: false },
];

const PROCESS_GATE: ProcessGateResponse = {
  engine: "community",
  enterprise_available: false,
  verify_state: "ok",
  enterprise_note: null,
  community_models_ready: true,
};

const PROCESS_TYPES: ProcessTypeRow[] = [
  {
    id: 1,
    name: "Purchase over threshold",
    active: true,
    levels: 2,
    chain: [
      { level: 1, min_approvals: 2, approver_user_ids: [2, 3] },
      { level: 2, min_approvals: 1, approver_user_ids: [4] },
    ],
  },
];

const PROCESS_REQUESTS: ProcessRequestRow[] = [
  {
    id: 10,
    name: "PR-0010",
    subject: "Laptops for Lagos office",
    amount: 4200,
    state: "submitted",
    current_level: 1,
    type_id: 1,
    requester_id: 2,
  },
  {
    id: 11,
    name: "PR-0011",
    subject: "Office chairs",
    amount: 800,
    state: "draft",
    current_level: null,
    type_id: 1,
    requester_id: 2,
  },
];

type HarnessState =
  | "default"
  | "empty"
  | "error"
  | "loading"
  | "processes"
  | "studio"
  | "pending";

const KNOWN: HarnessState[] = [
  "default",
  "empty",
  "error",
  "loading",
  "processes",
  "studio",
  "pending",
];

export default function ApprovalsE2ePage() {
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
  return <ApprovalsHarness key={state} state={state} />;
}

function ApprovalsHarness({ state }: { state: HarnessState }) {
  const gate = state === "studio" ? STUDIO_GATE : GATE;
  const [tab, setTab] = useState<ApprovalsTab>(state === "processes" ? "processes" : "buttons");
  const [form, setForm] = useState<ApprovalRuleForm>(() => ({
    ...defaultApprovalRuleForm(),
    buttonMethod: state === "empty" ? "" : "action_confirm",
  }));
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState<string | null>(
    state === "default" ? "Odoo approval rule deployed." : null,
  );
  const rules = state === "empty" || state === "error" ? [] : RULES;
  const entries =
    state === "empty" || state === "error"
      ? []
      : state === "pending"
        ? ENTRIES
        : ENTRIES.filter((e) => e.status !== "pending");
  const loading = state === "loading";
  const showError = state === "error";

  const buttonsPane = (
    <>
      <p className="ap-lead">
        Studio-style button gating. Uses Community rules by default; Enterprise Studio when
        detected.
      </p>
      {showError ? (
        <div className="mt-4">
          <ApprovalsStateGuide
            tone="danger"
            live
            testId="approvals-error"
            guide={{
              ...approvalsErrorGuide("load"),
              why: "Odoo RPC error: Access Denied for approval rule read",
            }}
            actions={
              <Button type="button" variant="secondary" size="sm">
                Retry
              </Button>
            }
          />
        </div>
      ) : null}
      {notice ? (
        <Callout variant="info" title="Notice" className="mt-4" testId="approvals-notice">
          {notice}
        </Callout>
      ) : null}
      <ApprovalRuleComposer
        form={form}
        buttons={BUTTONS}
        busy={false}
        onChange={(next) => setForm((f) => ({ ...f, ...next }))}
        onDiscover={() => setNotice("Discovered 2 buttons on " + form.model)}
        onDeploy={(e: FormEvent) => {
          e.preventDefault();
          setNotice("Odoo approval rule deployed.");
        }}
      />
      <ApprovalRulesList
        rules={rules}
        loading={loading}
        busy={false}
        query={query}
        testRecordId={form.testRecordId}
        onQueryChange={setQuery}
        onTestRecordIdChange={(value) => setForm((f) => ({ ...f, testRecordId: value }))}
        onSimulate={(ruleId) => setNotice(`Simulated click for ${ruleId}`)}
        onOpenComposer={() =>
          document.getElementById("approval-new-rule")?.scrollIntoView({ behavior: "smooth" })
        }
      />
      <ApprovalEntriesList
        entries={entries}
        loading={loading}
        busy={false}
        onRefresh={() => setNotice("Entries refreshed.")}
        onResolve={(id, approve) =>
          setNotice(approve ? `Approved ${id}` : `Rejected ${id}`)
        }
      />
    </>
  );

  const processesPane = useMemo(() => {
    const empty = state === "empty";
    const types = empty ? [] : PROCESS_TYPES;
    const requests = empty ? [] : PROCESS_REQUESTS;
    return (
      <div data-testid="approval-processes-panel">
        <p className="ap-lead">
          Standalone request and approve workflows with multi-level chains. Distinct from button
          gating on the Rules tab.
        </p>
        <div className="ap-honesty" data-testid="approval-processes-engine">
          <span className="ap-chip">{processEngineLabel(PROCESS_GATE.engine)}</span>
          <span className="ap-chip" data-tone="accent">
            Models ready
          </span>
        </div>
        <section className="ap-composer" data-testid="approval-process-composer">
          <h3 className="ap-composer-title">New request</h3>
          <div className="ap-composer-grid">
            <Select
              label="Type"
              value={types[0] ? String(types[0].id) : ""}
              onChange={() => undefined}
              placeholder="Select a type"
              options={types.map((t) => ({
                value: String(t.id),
                label: `${t.name} (${t.levels} level(s))`,
              }))}
            />
            <Input label="Subject" defaultValue="Purchase request" />
            <Input label="Amount" defaultValue="1000" />
            <Input label="Actor user id" defaultValue="2" />
          </div>
          <div className="ap-composer-actions">
            <Button type="button" variant="primary" size="sm" disabled={empty}>
              Create draft request
            </Button>
          </div>
        </section>
        <section className="ap-section" data-testid="approval-process-types">
          <h3 className="ap-list-title">Approval types</h3>
          {types.length === 0 ? (
            <div className="mt-3">
              <ApprovalsStateGuide
                testId="approval-process-types-empty"
                guide={processesEmptyGuide("types")}
              />
            </div>
          ) : (
            <ul className="ap-list">
              {types.map((t) => (
                <li key={t.id}>
                  <div className="ap-list-row">
                    <div className="min-w-0">
                      <p className="ap-list-name">{t.name}</p>
                      <p className="ap-list-meta" style={{ fontFamily: "inherit" }}>
                        {t.levels} level(s) · L1 min {t.chain[0]?.min_approvals}
                      </p>
                    </div>
                    <Badge variant="success">Active</Badge>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="ap-section" data-testid="approval-process-requests">
          <h3 className="ap-list-title">Requests</h3>
          {requests.length === 0 ? (
            <div className="mt-3">
              <ApprovalsStateGuide
                testId="approval-process-requests-empty"
                guide={processesEmptyGuide("requests")}
              />
            </div>
          ) : (
            <ul className="ap-list">
              {requests.map((r) => (
                <li key={r.id}>
                  <div className="ap-list-row">
                    <div className="min-w-0">
                      <p className="ap-list-name">
                        #{r.id} {r.subject}
                      </p>
                      <div className="ap-list-actions">
                        {r.state === "draft" ? (
                          <Button type="button" variant="secondary" size="sm">
                            Send for approval
                          </Button>
                        ) : null}
                        {r.state === "submitted" ? (
                          <>
                            <Button type="button" variant="secondary" size="sm">
                              Approve
                            </Button>
                            <Button type="button" variant="secondary" size="sm">
                              Refuse
                            </Button>
                          </>
                        ) : null}
                      </div>
                    </div>
                    <Badge variant="info">{r.state}</Badge>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    );
  }, [state]);

  return (
    <div data-testid="approvals-harness-root">
    <OperateStudioChrome
      testIdPrefix="approvals"
      pageTestId="approvals-harness"
      kicker="E2E harness"
      title="Odoo approval rules"
      subtitle="Gate form buttons behind approvers on this Odoo connection."
      badge={{ label: "Ready", variant: "default" }}
      honesty={{
        title: "Community engine",
        why: "Deploy button rules here. Approvers act in the Approval inbox.",
        next: "Open Button rules, then deploy.",
      }}
      shellClassName="approvals-operate"
      className="p-4 sm:p-6"
    >
      <p className="ap-inbox-note">{INBOX_HINT}</p>
      <span className="sr-only" data-testid="approvals-honesty">honesty</span>

      <div className="ap-tabs">
        <Tabs
          value={tab}
          onValueChange={(v) => setTab(v as ApprovalsTab)}
          items={[
            { value: "buttons", label: "Button rules", content: buttonsPane },
            { value: "processes", label: "Approval processes", content: processesPane },
          ]}
        />
      </div>
    </OperateStudioChrome>
    </div>
  );
}
