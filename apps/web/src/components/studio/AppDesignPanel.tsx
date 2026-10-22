"use client";

import { isOdooOnlineUrl, odooAppsUrl } from "@/lib/odoo-online-url";
import { useState } from "react";
import { api } from "@/lib/api";
import { AgentPlayback } from "@/components/studio/AgentPlayback";
import { DesignPreview } from "@/components/studio/DesignPreview";
import type { StudioAppDesign, StudioDesignField, StudioAutomation } from "@/lib/studio-session";

const RELATIONAL = new Set(["many2one", "one2many", "many2many"]);

const SOURCE_LABEL: Record<string, string> = {
  llm: "Designed by AI",
  llm_repaired: "AI design, repaired",
  outline: "Rough outline from your headings",
};

const STOCK_LABEL: Record<string, string> = {
  "res.partner": "Contacts",
  "sale.order": "Sales",
  "crm.lead": "CRM",
  "account.move": "Invoicing",
  "project.project": "Project",
  "project.task": "Project tasks",
  "helpdesk.ticket": "Helpdesk",
  "res.users": "Users",
  "product.product": "Products",
};

const CONTRACT_DECISION_LABEL: Record<string, string> = {
  metadata: "Fields, views, or standard automation",
  stock_automation: "Standard automation (no custom code)",
  option_a: "Custom code module",
  clarify: "Needs your choice",
  declined: "Left out at your request",
};

/* ---------- pure edit helpers (also used by tests) ---------- */

export function renameApp(design: StudioAppDesign, name: string): StudioAppDesign {
  return { ...design, app_name: name };
}

export function renameModel(design: StudioAppDesign, model: string, label: string): StudioAppDesign {
  return {
    ...design,
    new_models: design.new_models.map((m) => (m.name === model ? { ...m, label } : m)),
  };
}

/** Remove a model and every link pointing at it (the backend re-validates anyway). */
export function removeModel(design: StudioAppDesign, model: string): StudioAppDesign {
  if (design.new_models.length <= 1) return design;
  const dropLinks = (fields: StudioDesignField[]) => fields.filter((f) => f.relation !== model);
  return {
    ...design,
    new_models: design.new_models
      .filter((m) => m.name !== model)
      .map((m) => ({ ...m, fields: dropLinks(m.fields) })),
    stock_extensions: (design.stock_extensions || [])
      .map((e) => ({ ...e, fields: dropLinks(e.fields) }))
      .filter((e) => e.fields.length > 0),
    security_groups: (design.security_groups || []).map((g) => {
      const access = { ...(g.access || {}) };
      delete access[model];
      return { ...g, access };
    }),
    python_needed: (design.python_needed || []).map((p) => ({
      ...p,
      models: (p.models || []).filter((m) => m !== model),
    })),
    automations: (design.automations || []).filter((a) => a.target_model !== model),
  };
}

export function removeField(design: StudioAppDesign, owner: string, field: string): StudioAppDesign {
  return {
    ...design,
    new_models: design.new_models.map((m) =>
      m.name === owner ? { ...m, fields: m.fields.filter((f) => f.name !== field) } : m,
    ),
    stock_extensions: (design.stock_extensions || []).map((e) =>
      e.model === owner ? { ...e, fields: e.fields.filter((f) => f.name !== field) } : e,
    ),
  };
}

export function removeAutomation(design: StudioAppDesign, id: string): StudioAppDesign {
  return {
    ...design,
    automations: (design.automations || []).filter((a) => a.requirement_id !== id),
    automations_off: [...new Set([...(design.automations_off || []), id])],
  };
}

function automationSummary(a: StudioAutomation): string {
  const s = a.automation;
  if (!s) return "";
  const todo = s.action === "activity" ? "schedule a to-do" : String(s.action || "");
  if (s.when === "on_time") {
    const days = Math.abs(s.offset_days || 0);
    const when = !days
      ? `On ${s.date_field || "the date"}`
      : `${days} day${days === 1 ? "" : "s"} ${(s.offset_days || 0) < 0 ? "before" : "after"} ${s.date_field || "the date"}`;
    return `${when}: ${todo}`;
  }
  return `${s.when === "on_create" ? "When created" : "When changed"}: ${todo}`;
}

export function toggleIntegration(design: StudioAppDesign, module: string): StudioAppDesign {
  const off = new Set(design.integrations_off || []);
  if (off.has(module)) off.delete(module);
  else off.add(module);
  return { ...design, integrations_off: [...off] };
}

export function putBackLeftOut(design: StudioAppDesign, id: string): StudioAppDesign {
  return { ...design, left_out: (design.left_out || []).map((r) => (r.id === id ? { ...r, put_back: true } : r)) };
}

export function toggleChoice(design: StudioAppDesign, id: string): StudioAppDesign {
  return {
    ...design,
    checklist_choices: (design.checklist_choices || []).map((r) => (r.id === id ? { ...r, ticked: r.ticked === false } : r)),
  };
}

export function designIsOnlineBlocked(design: StudioAppDesign | null | undefined): boolean {
  // The API may send the lane flag as a boolean or as "true"/"false".
  return Boolean(design?.python_needed?.some((p) => p.online_blocked === true || p.online_blocked === "true"));
}

/* ---------- display helpers ---------- */

function labelOf(design: StudioAppDesign, model: string): string {
  return (
    design.new_models.find((m) => m.name === model)?.label ||
    STOCK_LABEL[model] ||
    model
  );
}

function fieldType(f: StudioDesignField, design: StudioAppDesign): string {
  if (RELATIONAL.has(f.ttype) && f.relation) return `${f.ttype} → ${labelOf(design, f.relation)}`;
  return f.ttype;
}

function relationsOf(design: StudioAppDesign) {
  const rows: { key: string; from: string; to: string; type: string }[] = [];
  const owners: [string, StudioDesignField[]][] = [
    ...design.new_models.map((m) => [m.name, m.fields] as [string, StudioDesignField[]]),
    ...(design.stock_extensions || []).map((e) => [e.model, e.fields] as [string, StudioDesignField[]]),
  ];
  for (const [owner, fields] of owners) {
    for (const f of fields) {
      if (RELATIONAL.has(f.ttype) && f.relation) {
        rows.push({ key: `${owner}.${f.name}`, from: labelOf(design, owner), to: labelOf(design, f.relation), type: f.ttype });
      }
    }
  }
  return rows;
}

/* ---------- components ---------- */

export function BuildCustomCodeButton({
  design,
  busy,
  onBuild,
}: {
  design: StudioAppDesign;
  busy?: boolean;
  onBuild?: () => void;
}) {
  const pieces = design.python_needed || [];
  if (!pieces.length) return null;
  if (designIsOnlineBlocked(design)) {
    const note = pieces.find((p) => p.lane_note)?.lane_note;
    return (
      <p className="clarify-help app-design-lane-note" data-testid="studio-custom-code-online-note">
        {note || "Odoo Online can't install custom Python. Move to Odoo.sh or your own server to add it."}
      </p>
    );
  }
  if (!onBuild) {
    return (
      <p className="clarify-help app-design-lane-note">
        After Generate, use Build custom code: build and test, then Promote.
      </p>
    );
  }
  return (
    <button
      type="button"
      className="btn btn-secondary btn-sm"
      disabled={busy}
      data-testid="studio-build-custom-code"
      onClick={onBuild}
    >
      Build custom code
    </button>
  );
}

export function editAssumption(design: StudioAppDesign, index: number, chosen: string): StudioAppDesign {
  const list = [...(design.assumptions || [])];
  const row = list[index];
  if (!row) return design;
  const text = chosen.trim();
  list[index] = { ...row, chosen: text || undefined };
  return { ...design, assumptions: list };
}

export function AppDesignPanel({
  design,
  busy,
  onChange,
  onBuildCustomCode,
  summary,
  onRetryDesign,
  connectionId,
  isOdooOnline,
  odooUrl,
  sessionId,
}: {
  design: StudioAppDesign;
  busy?: boolean;
  onChange?: (next: StudioAppDesign) => void;
  onBuildCustomCode?: () => void;
  /** Summary already shown above the panel; the purpose is hidden when it repeats it. */
  summary?: string;
  onRetryDesign?: () => void;
  connectionId?: string;
  isOdooOnline?: boolean;
  odooUrl?: string;
  /** Agent mode: lets the owner send playback edits back for a re-design. */
  sessionId?: string;
}) {
  const [installing, setInstalling] = useState<string | null>(null);
  const [installError, setInstallError] = useState<string | null>(null);
  const norm = (v?: string) => (v || "").replace(/\s+/g, " ").trim().toLowerCase();
  const showPurpose =
    Boolean(design.purpose) &&
    !(summary && (norm(summary).startsWith(norm(design.purpose).slice(0, 80)) ||
      norm(design.purpose).startsWith(norm(summary).slice(0, 80))));
  const fallbackReason = typeof design.fallback_reason === "string" ? design.fallback_reason : "";
  const appsUrl = odooAppsUrl(odooUrl);
  const online = Boolean(isOdooOnline) || isOdooOnlineUrl(odooUrl);
  async function install(module: string) {
    if (!connectionId) {
      setInstallError("Open App Studio from a connection to install apps.");
      return;
    }
    setInstalling(module);
    setInstallError(null);
    try {
      await api.installCommunityModule(connectionId, module);
      onRetryDesign?.();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      setInstallError(
        /dry_run|receipt/i.test(msg) || !msg
          ? "Ingenium couldn't install the app. Try again, or install it from Odoo's Apps screen."
          : msg,
      );
    } finally {
      setInstalling(null);
    }
  }
  const editable = Boolean(onChange) && !busy;
  const off = new Set(design.integrations_off || []);
  const relations = relationsOf(design);
  const sourceLabel = SOURCE_LABEL[String(design.source || "")] || null;
  const edit = (next: StudioAppDesign) => onChange?.(next);
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const suggestions = (design.stock_suggestions || []).filter((a) => !a.installed);
  const assumptions = design.assumptions || [];
  const outOfScope = design.out_of_scope || [];

  return (
    <div className="app-design" data-testid="studio-app-design">
      <div className="diagnosis-field app-design-head">
        <span>
          App design
          {sourceLabel ? (
            <em className="app-design-source" data-testid="studio-app-design-source">
              {sourceLabel}
            </em>
          ) : null}
        </span>
        <input
          className="input"
          aria-label="App name"
          disabled={!editable}
          value={design.app_name}
          onChange={(e) => edit(renameApp(design, e.target.value))}
        />
        {showPurpose ? <p className="clarify-help app-design-purpose">{design.purpose}</p> : null}
      </div>
      <AgentPlayback design={design} onChange={editable ? edit : undefined} sessionId={sessionId} />
      <DesignPreview design={design} connectionId={connectionId} />
      {design.source === "outline" ? (
        <div className="diagnosis-field" data-testid="studio-app-design-fallback" role="status">
          <p className="clarify-help">
            The AI design didn&apos;t come through, so this is a rough outline from your headings.
            {fallbackReason ? ` ${fallbackReason}` : ""} Try again for a full design.
          </p>
          {onRetryDesign ? (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={busy}
              data-testid="studio-app-design-retry"
              onClick={onRetryDesign}
            >
              Try the design again
            </button>
          ) : null}
        </div>
      ) : null}

      {assumptions.length ? (
        <div className="diagnosis-field" data-testid="studio-assumptions">
          <span>Choices we made for you</span>
          <ul className="diagnosis-facts">
            {assumptions.map((a, i) => (
              <li key={`${a.requirement_id || "a"}-${i}`} data-testid="studio-assumption">
                {a.chosen ? <>You chose: {a.chosen}</> : a.text}
                {editing === i ? (
                  <span className="app-design-inline-edit">
                    {(a.alternatives || []).map((alt) => (
                      <button key={alt} type="button" className="btn btn-secondary btn-sm"
                        onClick={() => { edit(editAssumption(design, i, alt)); setEditing(null); }}>
                        {alt}
                      </button>
                    ))}
                    <input className="input" aria-label="Your choice" placeholder="Or type what you want"
                      value={draft} onChange={(e) => setDraft(e.target.value)} />
                    <button type="button" className="btn btn-primary btn-sm" disabled={!draft.trim()}
                      onClick={() => { edit(editAssumption(design, i, draft)); setEditing(null); setDraft(""); }}>
                      Save
                    </button>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing(null)}>
                      Cancel
                    </button>
                  </span>
                ) : editable ? (
                  <button type="button" className="btn btn-ghost btn-sm" data-testid="studio-assumption-edit"
                    onClick={() => { setEditing(i); setDraft(a.chosen || ""); }}>
                    Edit
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {suggestions.length ? (
        <div className="diagnosis-field" data-testid="studio-stock-suggestions">
          <span>Odoo apps that already do part of this</span>
          <ul className="diagnosis-facts">
            {suggestions.map((a) => (
              <li key={a.module}>
                <strong>{a.name}</strong>: {a.why}
                {a.quote ? <span className="app-design-muted"> · Your brief: “{a.quote}”</span> : null}
                {a.available === false ? (
                  <span className="app-design-muted"> · Needs Odoo Enterprise</span>
                ) : online ? (
                  <a className="btn btn-secondary btn-sm" href={appsUrl || undefined} target="_blank" rel="noreferrer">
                    Install in Odoo
                  </a>
                ) : (
                  <button type="button" className="btn btn-secondary btn-sm" data-testid="studio-stock-install"
                    disabled={busy || installing === a.module} onClick={() => install(a.module)}>
                    {installing === a.module ? `Installing ${a.name}…` : `Install ${a.name}`}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {design.stock_checks?.length ? (
        <section className="diagnosis-field checklist-group" data-testid="studio-stock-checks" aria-labelledby="stock-h">
          <span id="stock-h">Built on Odoo</span>
          <ul className="checklist-rows">
            {design.stock_checks.map((r, n) => (
              <li key={r.id || n} className="checklist-row">
                <div className="checklist-row-text">
                  <strong>{r.item}</strong>
                  <span className="checklist-quote">{r.label}</span>
                </div>
                {r.install ? <span className="checklist-tag">Needs install</span> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {design.integration_routes?.length ? (
        <section className="diagnosis-field checklist-group" data-testid="studio-integration-routes" aria-labelledby="routes-h">
          <span id="routes-h">Outside services</span>
          <ul className="checklist-rows">
            {design.integration_routes.map((r) => (
              <li key={r.service} className="checklist-row">
                <div className="checklist-row-text">
                  <strong>{r.service}</strong>
                  <span className="checklist-quote">{r.label}</span>
                </div>
                {r.route === "decline" ? <span className="checklist-tag checklist-tag-warn">Not connected</span> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {(design.left_out || []).filter((r) => !r.put_back).length ? (
        <section className="diagnosis-field checklist-group" data-testid="studio-left-out" aria-labelledby="left-out-h">
          <span id="left-out-h">Left out</span>
          <ul className="checklist-rows">
            {(design.left_out || []).filter((r) => !r.put_back).map((r) => (
              <li key={r.id} className="checklist-row">
                <div className="checklist-row-text">
                  <strong>{r.item}</strong>
                  <span className="checklist-quote">{r.status === "cannot" && r.message ? r.message : `You said “${r.quote}”`}</span>
                </div>
                {onChange ? (
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm checklist-action"
                    disabled={busy}
                    aria-label={`Put ${r.item} back in the app`}
                    onClick={() => onChange(putBackLeftOut(design, r.id))}
                  >
                    Put back
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <p className="sr-only" aria-live="polite">
        {(design.left_out || []).filter((r) => r.put_back).map((r) => `${r.item} is back in the app.`).join(" ")}
      </p>

      {design.checklist_choices?.length ? (
        <section className="diagnosis-field checklist-group" data-testid="studio-checklist-choices" aria-labelledby="choices-h">
          <span id="choices-h">We weren’t sure about these</span>
          <p className="clarify-help">They’re in the app for now. Untick any you don’t want.</p>
          <ul className="checklist-rows">
            {design.checklist_choices.map((r) => (
              <li key={r.id} className="checklist-row">
                <label className="checklist-row-text checklist-choice">
                  <input
                    type="checkbox"
                    checked={r.ticked !== false}
                    disabled={busy || !onChange}
                    onChange={() => onChange?.(toggleChoice(design, r.id))}
                  />
                  <span>
                    <strong>{r.item}</strong>
                    <span className="checklist-quote">You said “{r.quote}”</span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {outOfScope.length ? (
        <div className="diagnosis-field" data-testid="studio-out-of-scope">
          <span>Not part of this app</span>
          <p className="clarify-help">
            To keep it simple, this app leaves out: {outOfScope.join("; ")}. Ask for any of these separately.
          </p>
        </div>
      ) : null}

      {design.intent_contract?.length ? (
        <div className="diagnosis-field" data-testid="studio-intent-contract">
          <span>Requirements checked</span>
          <ul className="diagnosis-facts">
            {design.intent_contract.map((row) => (
              <li key={row.id}>
                {row.subject}: {CONTRACT_DECISION_LABEL[row.decision] || row.decision}
                {row.evidence?.quote ? (
                  <span className="app-design-muted"> · Brief: “{row.evidence.quote}”</span>
                  
                ) : null}
                {row.origin === "inferred" ? (
                  <span className="app-design-muted"> · Suggested by App Studio</span>
                ) : null}
                {row.downgrade_reason ? (
                  <span className="app-design-muted"> · {row.downgrade_reason}</span>
                ) : null}                
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {design.critic_findings?.length ? (
        <div className="diagnosis-field" data-testid="studio-intent-review">
          <span>Independent review</span>
          <ul className="diagnosis-facts">
            {design.critic_findings.map((finding) => (
              <li key={finding.id}>
                {finding.subject}
                {finding.detail ? `: ${finding.detail}` : null}
                {finding.evidence?.quote ? (
                  <span className="app-design-muted"> · Brief: “{finding.evidence.quote}”</span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="diagnosis-field">
        <span>New models ({design.new_models.length})</span>
        <ul className="app-design-cards">
          {design.new_models.map((m) => (
            <li key={m.name} className="app-design-card" data-testid="studio-app-design-model">
              <div className="app-design-card-head">
                <input
                  className="input app-design-card-label"
                  aria-label={`Name for ${m.name}`}
                  disabled={!editable}
                  value={m.label}
                  onChange={(e) => edit(renameModel(design, m.name, e.target.value))}
                />
                {m.is_config ? <span className="app-design-badge">Config</span> : null}
                {m.suggested ? (
                  <span className="app-design-badge app-design-badge--suggested" data-testid="studio-app-design-suggested">
                    Suggested
                  </span>
                ) : null}
                {editable && design.new_models.length > 1 ? (
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    aria-label={`Remove ${m.label}`}
                    onClick={() => edit(removeModel(design, m.name))}
                  >
                    Remove
                  </button>
                ) : null}
              </div>
              {m.suggested ? (
                <p className="app-design-why app-design-suggested-note">
                  Suggested by AI, remove if you don&apos;t need it.
                </p>
              ) : null}
              {m.why && !(m.suggested && /^suggested\b/i.test(m.why)) ? (
                <p className="app-design-why">{m.why}</p>
              ) : null}
              <ul className="app-design-fields">
                {m.fields
                  .filter((f) => f.name !== "x_name")
                  .map((f) => (
                    <li key={f.name} className="app-design-field">
                      <span>{f.string || f.name}</span>
                      <code>{fieldType(f, design)}</code>
                      {editable ? (
                        <button
                          type="button"
                          className="app-design-x"
                          aria-label={`Remove field ${f.string || f.name} from ${m.label}`}
                          onClick={() => edit(removeField(design, m.name, f.name))}
                        >
                          ×
                        </button>
                      ) : null}
                    </li>
                  ))}
              </ul>
            </li>
          ))}
        </ul>
      </div>

      {relations.length ? (
        <div className="diagnosis-field">
          <span>How they connect</span>
          <ul className="diagnosis-facts app-design-relations" data-testid="studio-app-design-relations">
            {relations.map((r) => (
              <li key={r.key}>
                {r.from} → {r.to} <code>{r.type}</code>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {design.stock_extensions?.length ? (
        <div className="diagnosis-field">
          <span>Added to existing apps</span>
          <ul className="diagnosis-facts">
            {design.stock_extensions.map((e) => (
              <li key={e.model}>
                {STOCK_LABEL[e.model] || e.model} gets{" "}
                {e.fields.map((f) => f.string || f.name).join(", ")}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {design.integrations?.length ? (
        <div className="diagnosis-field">
          <span>Works with</span>
          <p className="clarify-help diagnosis-follow--tight">
            Other Odoo apps this design links to. Apps that aren&apos;t installed are left out for
            now; install them and try the design again to add their links.
          </p>
          <ul className="app-design-integrations">
            {design.integrations.map((i) => {
              const deferred = i.status === "deferred";
              const isOff = off.has(i.module);
              return (
                <li key={i.module || i.app} className="app-design-integration" data-testid="studio-app-design-integration">
                  <span
                    className={`app-design-chip${deferred ? " app-design-chip--deferred" : ""}${isOff ? " app-design-chip--off" : ""}`}
                  >
                    {i.app} · {isOff ? "Turned off" : deferred ? "Not installed" : i.status === "available" ? "Installed" : "Couldn't check"}
                  </span>
                  {!isOff && i.note && i.status !== "available" ? (
                    <span className="clarify-help app-design-note">{i.note}</span>
                  ) : null}
                  {deferred && !isOff ? (
                    online ? (
                      appsUrl ? (
                        <span className="clarify-help app-design-note">
                          On Odoo Online, apps are installed from Odoo&apos;s Apps screen, which shows
                          any change to your subscription first.{" "}
                          <a
                            href={appsUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="btn btn-primary btn-sm"
                            data-testid={`studio-install-link-${i.module}`}
                          >
                            Install {i.app} in Odoo
                          </a>
                          , then try the design again.
                        </span>
                      ) : null
                    ) : connectionId && editable ? (
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        disabled={installing !== null}
                        data-testid={`studio-install-${i.module}`}
                        onClick={() => void install(i.module)}
                      >
                        {installing === i.module ? `Installing ${i.app}…` : `Install ${i.app}`}
                      </button>
                    ) : null
                  ) : null}
                  {deferred && editable ? (
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => edit(toggleIntegration(design, i.module))}
                    >
                      {isOff ? "Keep for later" : "Leave out"}
                    </button>
                  ) : null}
                </li>
              );
            })}
          </ul>
          {installError ? <p className="clarify-help" role="alert">{installError}</p> : null}
        </div>
      ) : null}

      {design.security_groups?.length ? (
        <div className="diagnosis-field">
          <span>Who can use it</span>
          <ul className="diagnosis-facts">
            {design.security_groups.map((g) => (
              <li key={g.name}>
                {g.name}
                {g.implied?.length ? <span className="app-design-muted"> · includes {g.implied.join(", ")}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {design.automations?.length ? (
        <div className="diagnosis-field" data-testid="studio-app-design-automations">
          <span>Automations (no custom code)</span>
          <ul className="diagnosis-facts">
            {design.automations.map((a) => (
              <li key={a.requirement_id}>
                {a.label}
                <span className="app-design-muted"> · on {labelOf(design, a.target_model)}</span>
                {automationSummary(a) ? (
                  <span className="app-design-muted"> · {automationSummary(a)}</span>
                ) : null}
                {a.evidence?.quote ? (
                  <span className="app-design-muted"> · Brief: “{a.evidence.quote}”</span>
                ) : null}
                {editable ? (
                  <button
                    type="button"
                    className="app-design-x"
                    aria-label={`Remove automation ${a.label}`}
                    onClick={() => edit(removeAutomation(design, a.requirement_id))}
                  >
                    ×
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {design.python_needed?.length ? (
        <div className="diagnosis-field" data-testid="studio-app-design-code">
          <span>Custom code</span>
          <ul className="diagnosis-facts">
            {design.python_needed.map((p) => (
              <li key={p.key || p.label}>
                {p.label}
                {p.models?.length ? (
                  <span className="app-design-muted"> · on {p.models.map((m) => labelOf(design, m)).join(", ")}</span>
                ) : null}
                {p.evidence?.quote ? (
                  <span className="app-design-muted"> · Brief: “{p.evidence.quote}”</span>
                ) : null}
              </li>
            ))}
          </ul>
          <BuildCustomCodeButton design={design} busy={busy} onBuild={onBuildCustomCode} />
        </div>
      ) : null}
    </div>
  );
}
