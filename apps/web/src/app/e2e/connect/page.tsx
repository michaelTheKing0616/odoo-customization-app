"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { BrandMark } from "@/components/brand/BrandMark";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { ConnectApiKeyGuide } from "@/components/connect/ConnectApiKeyGuide";
import { ConnectChecklist } from "@/components/connect/ConnectChecklist";
import { ConnectStateGuide } from "@/components/connect/ConnectStateGuide";
import { ConnectStepRail } from "@/components/connect/ConnectStepRail";
import {
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  PRIMARY_CTA,
  PRIMARY_CTA_BUSY,
  PROBE_STAGES,
  connectErrorGuide,
  connectObserverNote,
  connectSecretTip,
  connectedGuide,
  emptyConnectGuide,
  type ConnectStepId,
} from "@/lib/connectScreen";
import "@/components/connect/connect-operate.css";

const STATES = [
  "empty",
  "credentials",
  "probing",
  "error-auth",
  "error-dns",
  "error-tls",
  "success",
] as const;
type HarnessState = (typeof STATES)[number];

function stepFor(state: HarnessState): ConnectStepId {
  if (state === "success") return "summary";
  if (state === "probing") return "probe";
  return "credentials";
}

function ConnectHarnessInner() {
  const searchParams = useSearchParams();
  const raw = searchParams.get("state") || "empty";
  const state = (STATES.includes(raw as HarnessState) ? raw : "empty") as HarnessState;
  const step = stepFor(state);
  const isOnline = state === "credentials" || state === "error-auth";
  const secretTip = connectSecretTip(isOnline);

  return (
    <div className="connect-operate-desk">
      <div
        className="connect-operate"
        data-testid="connect-page"
        data-harness-state={state}
      >
        <header className="cn-topbar">
          <BrandMark size={28} />
          <nav className="cn-topbar-links" aria-label="Connect navigation">
            <span>Sign in</span>
            <span>Create account</span>
          </nav>
        </header>

        <div className="cn-hero">
          <h1>{PAGE_TITLE}</h1>
          <p>{PAGE_DESCRIPTION}</p>
        </div>

        <ConnectStepRail current={step} />

        {state === "success" ? (
          <section className="cn-paper" data-testid="connect-first-win">
            <ConnectStateGuide
              testId="connect-connected-guide"
              tone="success"
              guide={connectedGuide({
                serverVersion: "19.0+e",
                capsMessage: "Community GA path ready.",
              })}
            />
            <ol className="cn-success-list">
              <li>
                <span>1</span>
                <span>
                  <strong>App Studio</strong> - describe what you need.
                </span>
              </li>
              <li>
                <span>2</span>
                <span>
                  <strong>Projects</strong> - keep the draft.
                </span>
              </li>
            </ol>
            <div className="cn-success-actions">
              <Button variant="primary" data-testid="connect-first-win-app-studio">
                Open App Studio
              </Button>
              <Button variant="secondary">Projects</Button>
              <Button variant="ghost">Overview</Button>
            </div>
          </section>
        ) : (
          <section className="cn-paper">
            <div className="cn-observer" data-testid="connect-honesty">
              <span className="cn-observer-mark" aria-hidden />
              <p data-testid="connect-honesty-title">{connectObserverNote()}</p>
            </div>

            <form id="connect-form" className="space-y-4" onSubmit={(e) => e.preventDefault()}>
              <ConnectChecklist
                input={{
                  url:
                    state === "error-dns"
                      ? "https://missing-host.invalid"
                      : isOnline
                        ? "https://acme.odoo.com"
                        : "http://127.0.0.1:8069",
                  dbName: state === "empty" ? "" : "acme",
                  username: state === "empty" ? "" : "admin@example.com",
                  password: state === "empty" || state === "credentials" ? "" : "secret",
                  verified: false,
                }}
              />
              <div className="cn-field-grid cn-cols-2">
                <Input label="Label" value={state === "empty" ? "" : "Acme"} readOnly />
                <Input label="Database" value={state === "empty" ? "" : "acme"} readOnly />
              </div>
              <Input
                label="Odoo URL"
                value={
                  state === "error-dns"
                    ? "https://missing-host.invalid"
                    : isOnline
                      ? "https://acme.odoo.com"
                      : "http://127.0.0.1:8069"
                }
                readOnly
              />
              <div className="cn-field-grid cn-cols-2">
                <Input
                  label="Username"
                  value={state === "empty" ? "" : "admin@example.com"}
                  readOnly
                />
                <Input
                  label="API key (preferred) or password"
                  type="password"
                  value={state === "empty" || state === "credentials" ? "" : "••••••••"}
                  readOnly
                  data-testid="connect-secret"
                />
              </div>

              {secretTip ? (
                <p className="cn-secret-tip" data-testid="connect-api-key-honesty">
                  {secretTip}
                </p>
              ) : null}

              <ConnectApiKeyGuide
                url={isOnline ? "https://acme.odoo.com" : "http://127.0.0.1:8069"}
                hosting={isOnline ? "online" : "self_hosted"}
                errorMessage={state === "error-auth" ? "Authentication failed" : null}
              />

              {state === "probing" ? (
                <div
                  className="cn-probe"
                  aria-busy="true"
                  role="status"
                  data-testid="connect-probe-progress"
                >
                  <p className="cn-probe-label">Checking version…</p>
                  <div className="cn-probe-track" aria-hidden>
                    <div className="cn-probe-fill" />
                  </div>
                  <ol className="cn-probe-stages" aria-label="Probe stages">
                    {PROBE_STAGES.map((label, i) => (
                      <li
                        key={label}
                        data-state={i < 1 ? "done" : i === 1 ? "current" : "todo"}
                      >
                        {label.replace("…", "")}
                      </li>
                    ))}
                  </ol>
                </div>
              ) : null}

              {state === "error-auth" ? (
                <ConnectStateGuide
                  testId="connect-error-guide"
                  tone="danger"
                  live
                  guide={connectErrorGuide("auth", "Authentication failed")}
                />
              ) : null}
              {state === "error-dns" ? (
                <ConnectStateGuide
                  testId="connect-error-guide"
                  tone="danger"
                  live
                  guide={connectErrorGuide("dns", "getaddrinfo ENOTFOUND missing-host.invalid")}
                />
              ) : null}
              {state === "error-tls" ? (
                <ConnectStateGuide
                  testId="connect-error-guide"
                  tone="danger"
                  live
                  guide={connectErrorGuide("tls", "certificate has expired")}
                />
              ) : null}

              <div className="cn-actions">
                <p className="cn-actions-hint">
                  Credentials are encrypted at rest. The secret field stays write-only after save.
                </p>
                <Button
                  type="submit"
                  variant="primary"
                  disabled={state === "probing"}
                  loading={state === "probing"}
                  data-testid="connect-add-btn"
                >
                  {state === "probing" ? PRIMARY_CTA_BUSY : PRIMARY_CTA}
                </Button>
              </div>
            </form>
          </section>
        )}

        <section className="cn-saved" data-testid="connect-saved-list">
          <div className="cn-saved-head">
            <h2>Saved connections</h2>
            <p>{state === "success" ? "1 saved" : "None yet"}</p>
          </div>
          {state === "success" ? (
            <ul className="cn-saved-paper">
              <li className="cn-row">
                <div className="cn-row-title">
                  <p>Acme</p>
                </div>
                <p className="cn-row-meta">https://acme.odoo.com · acme · 19.0+e</p>
              </li>
            </ul>
          ) : (
            <div className="cn-saved-paper">
              <div className="cn-saved-empty" data-testid="connect-empty-guide">
                <h3 data-testid="connect-empty-guide-title">{emptyConnectGuide().title}</h3>
                <p data-testid="connect-empty-guide-why">{emptyConnectGuide().why}</p>
                <p className="mt-3" data-testid="connect-empty-guide-next">
                  {emptyConnectGuide().next}
                </p>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default function ConnectE2EPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted">Loading connect harness…</div>}>
      <ConnectHarnessInner />
    </Suspense>
  );
}
