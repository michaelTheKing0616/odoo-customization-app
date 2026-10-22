"use client";

import { Suspense } from "react";
import { OperateStudioBar } from "@/components/operate-studio/OperateStudioBar";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { EmptyState, PageHeader } from "@/components/ui/layout-primitives";
import { SettingsErrorNotice } from "@/components/settings/SettingsErrorNotice";
import { SettingsStageRail } from "@/components/settings/SettingsStageRail";
import { SettingsStateGuide } from "@/components/settings/SettingsStateGuide";
import {
  BOOTSTRAP_CTA,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  sanitizeSettingsCopy,
  settingsSessionBadge,
  PRIMARY_CTA,
  SAVE_CTA,
  bootstrapSettingsGuide,
  emptySettingsGuide,
  idleSettingsGuide,
  revealedSettingsGuide,
  savedBrowserGuide,
  settingsHonestyGuide,
  type SettingsStepIndex,
} from "@/lib/settingsScreen";
import "@/components/settings/settings-operate.css";

const STATES = [
  "empty",
  "idle",
  "bootstrap",
  "revealed",
  "saved",
  "error",
] as const;
type HarnessState = (typeof STATES)[number];

function stepFor(state: HarnessState): SettingsStepIndex {
  if (state === "revealed") return 2;
  if (state === "empty" || state === "saved") return 3;
  if (state === "idle" || state === "bootstrap" || state === "error") return 1;
  return 1;
}

function SettingsHarnessInner() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const searchParams = useSearchParams();
  const raw = searchParams.get("state") || "idle";
  const state = (STATES.includes(raw as HarnessState) ? raw : "idle") as HarnessState;

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  const showBootstrap = state === "bootstrap";
  const showCreate = state === "empty" || state === "idle" || state === "revealed" || state === "saved";
  const showKeys =
    state === "idle" || state === "revealed" || state === "saved"
      ? "list"
      : state === "empty"
        ? "empty"
        : null;

  return (
    <div
      className="settings-operate op-studio-shell p-4 sm:p-6"
      data-testid="settings-page"
      data-harness-state={state}
    >

      <header className="op-studio" data-testid="settings-studio-chrome">
        <div className="op-titlebar">
          <div className="op-title-block">
            <p className="op-kicker">E2E mock connection</p>
            <h1 className="op-title">{PAGE_TITLE}</h1>
            <p className="op-subtitle">{PAGE_DESCRIPTION}</p>
          </div>
        </div>
        <OperateStudioBar
          testIdPrefix="settings"
          badge={settingsSessionBadge(stepFor(state))}
          honesty={settingsHonestyGuide()}
          sanitize={sanitizeSettingsCopy}
        />
        <SettingsStageRail step={stepFor(state)} />
      </header>

      <div className="op-desk">
        <div className="op-paper space-y-4">

      {state === "error" ? (
        <SettingsErrorNotice
          className="mt-4"
          message="Gateway timed out while loading auth status"
          context="load"
        />
      ) : null}

      {state === "saved" ? (
        <SettingsStateGuide
          className="mt-4"
          tone="accent"
          testId="settings-saved-guide"
          guide={savedBrowserGuide(false)}
          live
        />
      ) : null}

      {state === "revealed" ? (
        <SettingsStateGuide
          className="mt-4"
          tone="warning"
          testId="settings-revealed-guide"
          guide={revealedSettingsGuide()}
        />
      ) : null}

      {state === "bootstrap" ? (
        <SettingsStateGuide
          className="mt-4"
          tone="accent"
          testId="settings-bootstrap-guide"
          guide={bootstrapSettingsGuide()}
        />
      ) : null}

      {state === "empty" ? (
        <SettingsStateGuide
          className="mt-4"
          tone="accent"
          density="brief" testId="settings-empty-guide"
          guide={emptySettingsGuide()}
        />
      ) : null}

      {state === "idle" ? (
        <SettingsStateGuide
          density="brief"
          className="mt-4"
          tone="accent"
          testId="settings-idle-guide"
          guide={idleSettingsGuide()}
        />
      ) : null}

      <section className="stg-panel" data-testid="settings-status-panel">
        <h2 className="stg-panel-title">Status</h2>
        <p className="stg-panel-sub">How apps sign in to Ingenium, and whether the first key can still be created.</p>
        <ul className="stg-status-list">
          <li>
            Mode: <code>api_key</code> · enabled true
          </li>
          <li>Active keys: {showKeys === "list" ? 1 : 0}</li>
          <li>Env APP_API_KEY configured: false</li>
          <li>Bootstrap available: {String(showBootstrap)}</li>
        </ul>
        {showBootstrap ? (
          <div className="stg-actions">
            <Button type="button" variant="primary" data-testid="settings-bootstrap-btn">
              {BOOTSTRAP_CTA}
            </Button>
          </div>
        ) : null}
      </section>

      <section className="stg-panel" data-testid="settings-browser-panel">
        <h2 className="stg-panel-title">Browser key</h2>
        <p className="stg-panel-sub">
          Stored in localStorage on this device and sent as Authorization Bearer. Not synced to
          Ingenium servers.
        </p>
        <Input
          defaultValue={state === "saved" || state === "idle" || state === "revealed" ? "oc_harness_demo" : ""}
          placeholder="oc_…"
          autoComplete="off"
          className="font-mono text-sm"
          aria-label="Browser API key"
          readOnly
        />
        <div className="stg-actions">
          <Button type="button" variant="secondary" data-testid="settings-save-browser-btn">
            {SAVE_CTA}
          </Button>
        </div>
      </section>

      <section className="stg-panel" data-testid="settings-trust-panel">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="stg-panel-title" style={{ marginBottom: 0 }}>
            Trust and safety
          </h2>
          <Link href="/settings/trust-safety" className="stg-link">
            Open safety contract
          </Link>
        </div>
        <p className="stg-panel-sub" style={{ marginTop: 8, marginBottom: 0 }}>
          Permission model, reversibility table, blast-radius limits, and incident playbook.
        </p>
      </section>

      {showCreate ? (
        <section className="stg-panel" data-testid="settings-create-panel">
          <h2 className="stg-panel-title">Create key</h2>
          <p className="stg-panel-sub">
            The full secret appears once after create. Give each key a name you can revoke later.
          </p>
          <Input
            id="settings-new-key-name"
            aria-label="Key name"
            defaultValue="operator"
            readOnly
          />
          <div className="stg-actions">
            <Button type="button" variant="primary" data-testid="settings-create-key-btn">
              {PRIMARY_CTA}
            </Button>
          </div>
        </section>
      ) : null}

      {state === "revealed" ? (
        <section className="stg-panel" data-testid="settings-reveal-panel">
          <h2 className="stg-panel-title">New key (shown once)</h2>
          <p className="stg-panel-sub">
            Copy now. Ingenium keeps only a hash. This value cannot be retrieved later.
          </p>
          <div className="stg-reveal">
            <pre className="font-mono text-xs">oc_live_harness_reveal_once_demo_key</pre>
            <div className="stg-actions">
              <Button type="button" variant="secondary" size="sm" data-testid="settings-copy-key-btn">
                Copy key
              </Button>
            </div>
          </div>
        </section>
      ) : null}

      {showKeys === "list" ? (
        <section className="stg-panel" data-testid="settings-keys-panel">
          <h2 className="stg-panel-title">Keys</h2>
          <p className="stg-panel-sub">Active and revoked keys for this workspace.</p>
          <div className="stg-key-row">
            <span>
              operator <span className="font-mono text-muted">oc_ab12…</span>
            </span>
            <Button type="button" variant="ghost" size="sm" className="text-danger">
              Revoke
            </Button>
          </div>
          <div className="stg-key-row">
            <span>
              ci <span className="font-mono text-muted">oc_zz99…</span>
              <Badge variant="danger" className="ml-2">
                revoked
              </Badge>
            </span>
          </div>
        </section>
      ) : null}

      {showKeys === "empty" ? (
        <section className="stg-panel" data-testid="settings-keys-empty">
          <h2 className="stg-panel-title">Keys</h2>
          <div className="mt-3">
            <EmptyState
              title="No API keys yet"
              description="Keys you create appear here with their prefix and a Revoke button."
              action={
                <Button type="button" variant="secondary" size="sm">
                  Name a key
                </Button>
              }
            />
          </div>
        </section>
      ) : null}

      <section className="stg-panel" data-testid="settings-audit-panel">
        <h2 className="stg-panel-title">Audit log</h2>
        <p className="stg-panel-sub">Recent mutating API requests (POST, PUT, PATCH, DELETE).</p>
        {state === "empty" || state === "bootstrap" || state === "error" ? (
          <EmptyState
            title="No audit entries yet"
            description="Each POST, PUT, PATCH, or DELETE request to this API appears here with its status and duration."
          />
        ) : (
          <div className="stg-key-row font-mono text-xs">
            <span>
              <span className="text-accent">POST</span> /api/keys · 201 · 42ms
            </span>
          </div>
        )}
      </section>
        </div>
      </div>

    </div>
  );
}

export default function SettingsE2EPage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm text-muted">Loading harness…</main>}>
      <SettingsHarnessInner />
    </Suspense>
  );
}
