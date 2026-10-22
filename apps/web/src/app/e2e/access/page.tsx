"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AccessComposer } from "@/components/access/AccessComposer";
import { AccessMatrixPanel } from "@/components/access/AccessMatrixPanel";
import { AccessModelPicker } from "@/components/access/AccessModelPicker";
import { AccessRightsList } from "@/components/access/AccessRightsList";
import { AccessSessionBar } from "@/components/access/AccessSessionBar";
import { AccessStateGuide } from "@/components/access/AccessStateGuide";
import { AccessVersionStrip } from "@/components/access/AccessVersionStrip";
import { AccessWorkspaceTabs } from "@/components/access/AccessWorkspaceTabs";
import { RecordRulesList } from "@/components/access/RecordRulesList";
import { Button } from "@/components/ui/Button";
import { ListComposerShell } from "@/components/ui/ListComposerShell";
import { OperateStudioChrome } from "@/components/operate-studio/OperateStudioChrome";
import type {
  AccessMatrixOut,
  AccessRightRow,
  Connection,
  GroupRow,
  RecordRuleRow,
} from "@/lib/api";
import { defaultAccessForm } from "@/lib/accessForm";
import {
  accessErrorGuide,
  accessVersionFrame,
  accessWriteGate,
  type AccessTab,
  type StagedPerms,
} from "@/lib/accessScreen";
import "@/components/access/access-operate.css";

const GROUPS: GroupRow[] = [
  { id: 1, name: "Internal User", full_name: "User types / Internal User", share: false },
  { id: 2, name: "User", full_name: "Sales / User: Own Documents Only", share: false },
  { id: 3, name: "Administrator", full_name: "Sales / Administrator", share: false },
  { id: 5, name: "Manager", full_name: "Inventory / Manager", share: false },
  { id: 4, name: "Portal", full_name: "User types / Portal", share: true },
];

const RIGHTS: AccessRightRow[] = [
  {
    id: 7,
    name: "Partner internal",
    model: "res.partner",
    model_id: 11,
    group_id: 1,
    group_name: "Internal User",
    perm_read: true,
    perm_write: true,
    perm_create: true,
    perm_unlink: false,
    active: true,
  },
  {
    id: 8,
    name: "Partner sales admin",
    model: "res.partner",
    model_id: 11,
    group_id: 3,
    group_name: "Sales / Administrator",
    perm_read: true,
    perm_write: true,
    perm_create: true,
    perm_unlink: true,
    active: true,
  },
  {
    id: 9,
    name: "Partner portal",
    model: "res.partner",
    model_id: 11,
    group_id: 4,
    group_name: "Portal",
    perm_read: true,
    perm_write: false,
    perm_create: false,
    perm_unlink: false,
    active: true,
  },
  {
    id: 10,
    name: "Partner public read",
    model: "res.partner",
    model_id: 11,
    group_id: null,
    group_name: null,
    perm_read: true,
    perm_write: false,
    perm_create: false,
    perm_unlink: false,
    active: true,
  },
];

const RULES: RecordRuleRow[] = [
  {
    id: 3,
    name: "Own partners",
    model: "res.partner",
    model_id: 11,
    domain_force: "[('user_id', '=', user.id)]",
    group_ids: [2],
    perm_read: true,
    perm_write: true,
    perm_create: true,
    perm_unlink: true,
    active: true,
    global: false,
  },
  {
    id: 4,
    name: "Company partners",
    model: "res.partner",
    model_id: 11,
    domain_force: "['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]",
    group_ids: [],
    perm_read: true,
    perm_write: true,
    perm_create: true,
    perm_unlink: true,
    active: true,
    global: true,
  },
];

const MATRIX: AccessMatrixOut = {
  models: ["res.partner", "sale.order", "stock.picking"],
  groups: GROUPS,
  cells: [
    {
      model: "res.partner",
      group_id: null,
      access_id: 10,
      name: "Partner public read",
      perm_read: true,
      perm_write: false,
      perm_create: false,
      perm_unlink: false,
      active: true,
    },
    {
      model: "res.partner",
      group_id: 1,
      access_id: 7,
      name: "Partner internal",
      perm_read: true,
      perm_write: true,
      perm_create: true,
      perm_unlink: false,
      active: true,
    },
    {
      model: "res.partner",
      group_id: 3,
      access_id: 8,
      name: "Partner sales admin",
      perm_read: true,
      perm_write: true,
      perm_create: true,
      perm_unlink: true,
      active: true,
    },
    {
      model: "res.partner",
      group_id: 4,
      access_id: 9,
      name: "Partner portal",
      perm_read: true,
      perm_write: false,
      perm_create: false,
      perm_unlink: false,
      active: true,
    },
    {
      model: "sale.order",
      group_id: 2,
      access_id: 21,
      name: "Order user",
      perm_read: true,
      perm_write: true,
      perm_create: true,
      perm_unlink: false,
      active: true,
    },
    {
      model: "sale.order",
      group_id: 3,
      access_id: 22,
      name: "Order admin",
      perm_read: true,
      perm_write: true,
      perm_create: true,
      perm_unlink: true,
      active: true,
    },
    {
      model: "sale.order",
      group_id: 4,
      access_id: 23,
      name: "Order portal",
      perm_read: true,
      perm_write: false,
      perm_create: false,
      perm_unlink: false,
      active: true,
    },
    {
      model: "stock.picking",
      group_id: 5,
      access_id: 31,
      name: "Picking manager",
      perm_read: true,
      perm_write: true,
      perm_create: true,
      perm_unlink: true,
      active: true,
    },
    {
      model: "stock.picking",
      group_id: 1,
      access_id: 32,
      name: "Picking internal",
      perm_read: true,
      perm_write: false,
      perm_create: false,
      perm_unlink: false,
      active: true,
    },
  ],
};

const STAGED: StagedPerms = {
  "sale.order::2": { perm_unlink: true },
  "stock.picking::3": { perm_read: true },
  "res.partner::4": { perm_write: true },
};

type HarnessState =
  "legacy" | "staged" | "odoo20" | "plan" | "empty" | "error" | "unknown" | "lines" | "rules";

function harnessConnection(state: HarnessState): Connection {
  const major = state === "odoo20" ? 20 : 19;
  return {
    id: "demo-conn",
    name: "Lagos Sessions",
    url: "http://127.0.0.1:8069",
    db_name: "odoo",
    username: "admin",
    server_version: `${major}.0`,
    write_mode: state === "plan" ? "production" : "standard",
    created_at: null,
    updated_at: null,
    capabilities:
      state === "unknown"
        ? null
        : ({
            major,
            edition: "community",
            server_version: `${major}.0`,
            supported: [],
            unsupported: [],
            ga: true,
            message: "ok",
          } as unknown as Connection["capabilities"]),
  };
}

function AccessHarnessInner() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const params = useSearchParams();
  const state = (params.get("state") || "legacy") as HarnessState;
  const initialTab: AccessTab =
    state === "lines" ? "lines" : state === "rules" ? "rules" : "matrix";
  const [tab, setTab] = useState<AccessTab>(initialTab);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [models, setModels] = useState(
    state === "empty" ? "x_visitor_log" : MATRIX.models.join(", "),
  );
  const [saved, setSaved] = useState<string | null>(null);

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  const conn = harnessConnection(state);
  const major =
    state === "unknown" ? null : conn.capabilities ? (state === "odoo20" ? 20 : 19) : null;
  const frame = accessVersionFrame(major);
  const gate = accessWriteGate(conn, "demo-conn");
  const matrix = state === "empty" || state === "error" ? null : MATRIX;
  const error =
    state === "error"
      ? accessErrorGuide("Odoo RPC error: AccessError, not allowed to read ir.model.access")
      : null;
  const planHref = gate.mode === "plan" ? gate.planHref : null;

  return (
    <div data-testid="access-harness-root">
    <OperateStudioChrome
      testIdPrefix="access"
      pageTestId="access-harness"
      kicker="E2E harness"
      title="Access"
      subtitle="Who can read, write, create and delete each model."
      badge={{ label: "Ready", variant: "default" }}
      honesty={{
        title: "Who can read, write, create and delete each model.",
        why: "Access lines and record rules write to this live connection after confirm.",
        next: "Pick a model, edit the matrix, then Save.",
      }}
      shellClassName="access-operate"
      className="p-4 sm:p-6"
    >
      <AccessVersionStrip frame={frame} gate={gate} />
      {gate.mode !== "inline" ? (
        <AccessStateGuide
          guide={gate}
          tone={gate.mode === "plan" ? "warning" : "neutral"}
          testId="access-gate"
          className="mt-4"
        />
      ) : null}
      {error ? (
        <AccessStateGuide
          guide={error}
          tone="danger"
          live
          testId="access-error"
          className="mt-4"
          actions={
            <Button type="button" variant="secondary" size="sm" data-testid="access-error-retry">
              Retry
            </Button>
          }
        />
      ) : null}
      {saved ? (
        <p className="ax-notice" role="status" data-testid="access-notice">
          {saved}
        </p>
      ) : null}

      <AccessWorkspaceTabs
        tabs={frame.tabs}
        value={frame.tabs.includes(tab) ? tab : "matrix"}
        onChange={setTab}
        counts={{
          lines: state === "empty" ? 0 : RIGHTS.length,
          rules: state === "odoo20" ? 0 : RULES.length,
        }}
      >
        {(frame.tabs.includes(tab) ? tab : "matrix") === "matrix" ? (
          <AccessMatrixPanel
            frame={frame}
            gate={gate}
            modelsInput={models}
            onModelsInput={setModels}
            matrix={matrix}
            onLoad={() => undefined}
            initialStaged={state === "staged" ? STAGED : undefined}
            onSave={(changes) => {
              setSaved(
                `Saved ${changes.length} ${changes.length === 1 ? "right" : "rights"} to Odoo. A snapshot was taken first.`,
              );
              return true;
            }}
          />
        ) : tab === "rules" ? (
          <ListComposerShell
            className="!mt-0"
            animateDetail={false}
            list={
              <div className="grid gap-6">
                <AccessModelPicker
                  model="res.partner"
                  onModelChange={() => undefined}
                  onLoad={(e) => e.preventDefault()}
                />
                <RecordRulesList
                  rows={RULES}
                  model="res.partner"
                  selectedId={null}
                  query=""
                  onQueryChange={() => undefined}
                  onSelect={() => undefined}
                  onCreate={() => undefined}
                />
              </div>
            }
            detail={<p className="text-sm text-muted">Pick a rule to edit its domain.</p>}
          />
        ) : (
          <ListComposerShell
            className="!mt-0"
            animateDetail={false}
            list={
              <div className="grid gap-6">
                <AccessModelPicker
                  model="res.partner"
                  onModelChange={() => undefined}
                  onLoad={(e) => e.preventDefault()}
                />
                <AccessRightsList
                  rows={state === "empty" ? [] : RIGHTS}
                  model="res.partner"
                  title={frame.combined ? "ir.access rows" : "Access lines"}
                  selectedId={selectedId}
                  query={query}
                  onQueryChange={setQuery}
                  onSelect={(row) => setSelectedId(row.id)}
                  onCreate={() => setSelectedId(null)}
                />
              </div>
            }
            detail={
              <>
                <AccessSessionBar
                  sessionState="unsaved"
                  submitLabel={planHref ? "Plan card" : "Save right"}
                  canDiscard
                  onDiscard={() => undefined}
                />
                <AccessComposer
                  model="res.partner"
                  form={{ ...defaultAccessForm(), name: "Partner sales user", group_id: "2" }}
                  groups={GROUPS}
                  onChange={() => undefined}
                  onSubmit={(event) => event.preventDefault()}
                  planHref={planHref}
                />
              </>
            }
          />
        )}
      </AccessWorkspaceTabs>
    </OperateStudioChrome>
    </div>
  );
}

export default function AccessE2ePage() {
  return (
    <Suspense fallback={null}>
      <AccessHarnessInner />
    </Suspense>
  );
}
