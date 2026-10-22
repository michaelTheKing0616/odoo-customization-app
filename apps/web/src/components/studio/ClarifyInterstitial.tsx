"use client";

import { useEffect, useMemo, useState } from "react";
import type {
  StudioAppDesign,
  StudioApprovedCraft,
  StudioClarification,
  StudioCraftSmartButton,
  StudioUnderstanding,
} from "@/lib/studio-session";
import { SuggestionChip } from "./SuggestionChip";
import { StudioBusyLabel } from "./StudioBusyLabel";
import { AppDesignPanel } from "./AppDesignPanel";
import { InstallStepCard } from "./InstallStepCard";

export type DiagnosisPayload = StudioUnderstanding & { operator_note?: string };

type ClarifyInterstitialProps = {
  clarification: StudioClarification;
  busy?: boolean;
  onAnswer: (
    mergeKey: string,
    answerId: string,
    answerText?: string,
    understanding?: DiagnosisPayload,
  ) => void;
  onDismiss?: () => void;
  /** Run the diagnosis again (used when the AI design did not come through). */
  onRetryDesign?: () => void;
  /** S11: install the apps the design is built on, then re-check. */
  onInstallApps?: () => Promise<void>;
  /** The connection is read-only (observer): the install step shows that up front. */
  connectionReadOnly?: boolean;
  connectionId?: string;
  isOdooOnline?: boolean;
  odooUrl?: string;
  /** Agent mode re-design (playback edits). */
  sessionId?: string;
};

const HOST_FALLBACK: { id: string; label: string }[] = [
  { id: "sale.order", label: "Sales" },
  { id: "account.move", label: "Invoicing" },
  { id: "purchase.order", label: "Purchase" },
  { id: "stock.picking", label: "Inventory" },
  { id: "res.partner", label: "Contacts" },
  { id: "project.task", label: "Project" },
  { id: "crm.lead", label: "CRM" },
  { id: "hr.employee", label: "Employees" },
  { id: "calendar.event", label: "Calendar" },
];

const CRAFT_TOGGLE_DEFS: { key: keyof StudioApprovedCraft; label: string; help: string }[] = [
  {
    key: "company_scoping",
    label: "Company field on records",
    help: "Adds a company field on transactional models so each record can belong to one company.",
  },
  {
    key: "money_slots",
    label: "Currency field with amounts",
    help: "Adds a currency field when the draft has money amounts but no currency field yet.",
  },
  {
    key: "purchase_link",
    label: "Purchase order link",
    help: "Adds a purchase order link field on the record.",
  },
  {
    key: "partner_links",
    label: "Contact link",
    help: "Adds a contact link on the record beyond links your brief already named.",
  },
  {
    key: "datetime_over_date",
    label: "Date and time (not date only)",
    help: "Uses date-and-time fields instead of date-only when adding schedule-style slots.",
  },
  {
    key: "depth_seeds",
    label: "Extra supporting records",
    help: "Your brief is short, so App Studio can suggest a few supporting records. They are extras, not things you asked for.",
  },
];

type CraftKey = keyof StudioApprovedCraft;

/** Only offer an extra when it applies to this brief and design. */
export function relevantCraftKeys(
  design: StudioAppDesign | null,
  text: string,
): CraftKey[] {
  const t = text.toLowerCase();
  const models = design?.new_models ?? [];
  const fields = models.flatMap((m) => m.fields ?? []);
  const keys: CraftKey[] = [];
  // Multi-company in the brief is a requirement: the design adds the company field, so it is
  // never offered here as an optional extra that could be left off.
  const money = fields.some(
    (f) =>
      ["float", "monetary"].includes(String(f.ttype)) &&
      /revenue|value|amount|price|cost|fee|budget/i.test(`${f.name} ${f.string ?? ""}`),
  );
  const currency = fields.some(
    (f) => String(f.ttype) === "monetary" || /currency/i.test(`${f.name} ${f.relation ?? ""}`),
  );
  if (money && !currency) keys.push("money_slots");
  if (/\bpurchas|\bvendor|\bsupplier|procure/.test(t)) keys.push("purchase_link");
  if (models.length > 0 && !fields.some((f) => f.relation === "res.partner")) {
    keys.push("partner_links");
  }
  if (/appointment|booking|schedul|time slot|shift|\bslots?\b/.test(t)) keys.push("datetime_over_date");
  const shortBrief = t.trim().split(/\s+/).length < 120;
  if (models.length < 3 && shortBrief) keys.push("depth_seeds");
  return keys;
}

function emptyApprovedCraft(): StudioApprovedCraft {
  return {
    company_scoping: false,
    money_slots: false,
    purchase_link: false,
    partner_links: false,
    datetime_over_date: false,
    depth_seeds: false,
  };
}

function normalizeApprovedCraft(raw: StudioApprovedCraft | undefined): StudioApprovedCraft {
  const base = emptyApprovedCraft();
  if (!raw || typeof raw !== "object") return base;
  for (const row of CRAFT_TOGGLE_DEFS) {
    base[row.key] = Boolean(raw[row.key]);
  }
  return base;
}

function DiagnosisCard({
  clarification,
  busy,
  onAnswer,
  onRetryDesign,
  onInstallApps,
  connectionReadOnly,
  connectionId,
  isOdooOnline,
  odooUrl,
  sessionId,
}: {
  clarification: StudioClarification;
  busy?: boolean;
  onAnswer: ClarifyInterstitialProps["onAnswer"];
} & Pick<
  ClarifyInterstitialProps,
  "onRetryDesign" | "onInstallApps" | "connectionReadOnly" | "connectionId" | "isOdooOnline" | "odooUrl" | "sessionId"
>) {
  const step = clarification.install_step;
  const installStep = step && (step.apps?.length || step.refresh) ? step : null;
  const seed = clarification.understanding || {};
  const goldLocked = Boolean(seed.gold_artifact_id);
  const hosts = clarification.host_choices?.length ? clarification.host_choices : HOST_FALLBACK;
  const [title, setTitle] = useState(seed.title || "");
  const [hostModel, setHostModel] = useState(seed.host_model || "");
  const [inheritExisting, setInheritExisting] = useState(Boolean(seed.inherit_existing));
  const [needsModule, setNeedsModule] = useState(Boolean(seed.needs_module));
  const [constraints, setConstraints] = useState<string[]>(
    Array.isArray(seed.constraints) ? seed.constraints : [],
  );
  const [newConstraint, setNewConstraint] = useState("");
  const [operatorNote, setOperatorNote] = useState("");
  const seedDesign: StudioAppDesign | null =
    clarification.app_design || seed.app_design || null;
  const [design, setDesign] = useState<StudioAppDesign | null>(seedDesign);
  const [designEdited, setDesignEdited] = useState(false);
  const craftRows = useMemo(() => {
    const keys = relevantCraftKeys(
      design,
      [seed.title, seed.summary, design?.purpose, clarification.help, ...(seed.constraints ?? [])]
        .filter(Boolean)
        .join(" "),
    );
    return CRAFT_TOGGLE_DEFS.filter((row) => keys.includes(row.key));
  }, [design, seed.title, seed.summary, seed.constraints, clarification.help]);
  const seedCraft: StudioCraftSmartButton[] = Array.isArray(clarification.craft_proposals)
    ? clarification.craft_proposals
    : Array.isArray(seed.craft_proposals)
      ? seed.craft_proposals
      : [];
  const [craftKept, setCraftKept] = useState<StudioCraftSmartButton[]>(() =>
    seedCraft.filter((row) => row.default_on !== false),
  );
  const [approvedCraft, setApprovedCraft] = useState<StudioApprovedCraft>(() =>
    normalizeApprovedCraft(seed.approved_craft),
  );

  useEffect(() => {
    const next = clarification.understanding || {};
    setTitle(next.title || "");
    setHostModel(next.host_model || "");
    setInheritExisting(Boolean(next.inherit_existing));
    setNeedsModule(Boolean(next.needs_module));
    setConstraints(Array.isArray(next.constraints) ? next.constraints : []);
    setOperatorNote("");
    setNewConstraint("");
    const proposals: StudioCraftSmartButton[] = Array.isArray(clarification.craft_proposals)
      ? clarification.craft_proposals
      : Array.isArray(next.craft_proposals)
        ? next.craft_proposals
        : [];
    setCraftKept(proposals.filter((row) => row.default_on !== false));
    setApprovedCraft(normalizeApprovedCraft(next.approved_craft));
    setDesign(clarification.app_design || next.app_design || null);
    setDesignEdited(false);
  }, [clarification.understanding, clarification.craft_proposals, clarification.app_design]);

  const payload: DiagnosisPayload = useMemo(
    () => ({
      title: title.trim(),
      host_model: inheritExisting ? hostModel || null : null,
      inherit_existing: inheritExisting,
      needs_module: goldLocked ? true : needsModule,
      constraints,
      gold_artifact_id: seed.gold_artifact_id,
      craft_smart_buttons: craftKept,
      craft_proposals: seedCraft,
      approved_craft: approvedCraft,
      operator_note: operatorNote.trim() || undefined,
      // Only an edited design is sent back; the server re-validates it.
      ...(design && designEdited ? { app_design: design } : {}),
    }),
    [
      approvedCraft,
      design,
      designEdited,
      constraints,
      craftKept,
      goldLocked,
      hostModel,
      inheritExisting,
      needsModule,
      operatorNote,
      seed.gold_artifact_id,
      seedCraft,
      title,
    ],
  );

  const needsHostChoice = inheritExisting && !goldLocked && !hostModel;

  function addConstraint() {
    const row = newConstraint.trim();
    if (!row) return;
    setConstraints((prev) => (prev.includes(row) ? prev : [...prev, row].slice(0, 12)));
    setNewConstraint("");
  }

  function toggleCraft(key: keyof StudioApprovedCraft) {
    setApprovedCraft((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  return (
    <section
      className="card clarify-card clarify-card--diagnosis"
      data-testid="studio-diagnosis"
      aria-labelledby="studio-diagnosis-title"
    >
      <h2 id="studio-diagnosis-title" className="clarify-title">
        Check the diagnosis
      </h2>
      <p className="clarify-help clarify-lead">
        Here&apos;s what App Studio understood from your brief. Edit anything that looks wrong,
        then generate the form preview.
      </p>
      {clarification.help ? (
        <p className="clarify-help clarify-help--context">{clarification.help}</p>
      ) : null}
      <label className="diagnosis-field">
        <span>Name</span>
        <input
          className="input"
          value={title}
          disabled={busy}
          aria-label="Diagnosis title"
          onChange={(e) => setTitle(e.target.value)}
        />
      </label>
      <div className="diagnosis-field">
        <span>Where it lives</span>
        <div className="studio-chip-row">
          <SuggestionChip
            label="Existing form"
            selected={inheritExisting}
            disabled={busy || goldLocked}
            onClick={() => setInheritExisting(true)}
          />
          <SuggestionChip
            label="New app tile"
            selected={!inheritExisting}
            disabled={busy || goldLocked}
            onClick={() => setInheritExisting(false)}
          />
        </div>
        {inheritExisting ? (
          <select
            className="input diagnosis-follow"
            value={hostModel}
            disabled={busy}
            aria-label="Stock form"
            onChange={(e) => setHostModel(e.target.value)}
          >
            <option value="">Choose a form…</option>
            {hosts.map((row) => (
              <option key={row.id} value={row.id}>
                {row.label}
              </option>
            ))}
          </select>
        ) : (
          <p className="clarify-help diagnosis-follow">
            A new kind of record on the home screen.
          </p>
        )}
      </div>
      <div className="diagnosis-field">
        <span>How it is delivered</span>
        <div className="studio-chip-row">
          <SuggestionChip
            label="Custom-code module"
            selected={needsModule}
            disabled={busy || goldLocked}
            onClick={() => setNeedsModule(true)}
          />
          <SuggestionChip
            label="Built here, no custom code"
            selected={!needsModule}
            disabled={busy || goldLocked}
            onClick={() => setNeedsModule(false)}
          />
        </div>
        {goldLocked ? (
          <p className="clarify-help diagnosis-follow">
            Gold template {seed.gold_artifact_id} stays a module: download the zip, prove it in a
            sandbox, then Promote.
          </p>
        ) : needsModule ? (
          <p className="clarify-help diagnosis-follow">
            Built as Python and QWeb code, so it ships through Promote, not Install this app.
          </p>
        ) : inheritExisting ? (
          <p className="clarify-help diagnosis-follow">
            New fields on the form people already use.
          </p>
        ) : (
          <p className="clarify-help diagnosis-follow">
            Fields, views and menus built directly in your database.
            {design?.python_needed?.length
              ? " Pieces that need custom code are listed under Custom code and go through the custom-code path."
              : ""}
          </p>
        )}
      </div>
      <div className="diagnosis-field">
        <span>Must do</span>
        <ul className="diagnosis-facts">
          {constraints.map((row) => (
            <li key={row} className="diagnosis-constraint-row">
              <span>{row}</span>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={busy}
                aria-label={`Remove ${row}`}
                onClick={() => setConstraints((prev) => prev.filter((item) => item !== row))}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
        <div className="diagnosis-add-row">
          <input
            className="input"
            value={newConstraint}
            disabled={busy}
            placeholder="Add a requirement…"
            aria-label="Add requirement"
            onChange={(e) => setNewConstraint(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addConstraint();
              }
            }}
          />
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={busy || !newConstraint.trim()}
            onClick={addConstraint}
          >
            Add
          </button>
        </div>
      </div>
      {craftRows.length > 0 ? (
      <div className="diagnosis-field" data-testid="studio-diagnosis-approved-craft">
        <span>Optional extras (off by default)</span>
        <p className="clarify-help diagnosis-follow--tight">
          Turn one on only if you want Generate to add it even though your brief didn&apos;t ask.
        </p>
        <ul className="diagnosis-facts">
          {craftRows.map((row) => {
            const on = Boolean(approvedCraft[row.key]);
            return (
              <li key={row.key} className="diagnosis-constraint-row">
                <span>
                  {row.label}
                  <span className="clarify-help diagnosis-row-help">
                    {row.help}
                  </span>
                </span>
                <button
                  type="button"
                  className={`btn btn-sm btn-secondary btn-toggle${on ? " is-on" : ""}`}
                  disabled={busy}
                  aria-pressed={on}
                  aria-label={`${row.label}: ${on ? "on" : "off"}`}
                  data-testid={`studio-craft-toggle-${row.key}`}
                  onClick={() => toggleCraft(row.key)}
                >
                  {on ? "On" : "Off"}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
      ) : null}
      {seedCraft.length > 0 ? (
        <div className="diagnosis-field" data-testid="studio-diagnosis-nice-to-have">
          <span>Nice to have</span>
          <p className="clarify-help diagnosis-follow--tight">
            Optional smart buttons on stock forms. Remove any you don&apos;t want before you
            generate.
          </p>
          <ul className="diagnosis-facts">
            {craftKept.map((row) => {
              const chip = row.chip_label || `"${row.label}" on ${row.on_model}`;
              return (
                <li key={row.id || `${row.on_model}:${row.relation_field}`} className="diagnosis-constraint-row">
                  <span>{chip}</span>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    disabled={busy}
                    aria-label={`Remove ${chip}`}
                    data-testid={`studio-craft-remove-${row.on_model}`}
                    onClick={() =>
                      setCraftKept((prev) =>
                        prev.filter(
                          (item) =>
                            (item.id || `${item.on_model}:${item.relation_field}`) !==
                            (row.id || `${row.on_model}:${row.relation_field}`),
                        ),
                      )
                    }
                  >
                    Remove
                  </button>
                </li>
              );
            })}
          </ul>
          {craftKept.length === 0 ? (
            <p className="clarify-help">All optional smart buttons removed.</p>
          ) : null}
        </div>
      ) : null}
      {design && ((seedDesign?.new_models?.length ?? 0) > 1 || Boolean((design as { playback?: unknown }).playback)) ? (
        <AppDesignPanel
          sessionId={sessionId}
          design={design}
          busy={busy}
          summary={seed.summary}
          onRetryDesign={onRetryDesign}
          connectionId={connectionId}
          isOdooOnline={isOdooOnline}
          odooUrl={odooUrl}
          onChange={(next) => {
            setDesign(next);
            setDesignEdited(true);
          }}
        />
      ) : null}
      {installStep ? (
        <InstallStepCard
          step={installStep}
          busy={busy}
          onInstall={onInstallApps}
          readOnly={connectionReadOnly}
        />
      ) : null}
      <label className="diagnosis-field">
        <span>Anything to correct</span>
        <textarea
          className="textarea"
          rows={2}
          disabled={busy}
          placeholder="For example: put it on Purchase orders, not Sales. WHT is 5%."
          value={operatorNote}
          onChange={(e) => setOperatorNote(e.target.value)}
        />
      </label>
      <div className="clarify-actions">
        <button
          type="button"
          className="btn btn-primary"
          disabled={busy || needsHostChoice || Boolean(installStep)}
          aria-describedby={
            installStep
              ? "studio-diagnosis-install-hint"
              : needsHostChoice
                ? "studio-diagnosis-host-hint"
                : undefined
          }
          data-testid="studio-diagnosis-confirm"
          onClick={() =>
            // Answer text is the server-matched confirm phrase (understand.py); label above is UI only.
            onAnswer(clarification.merge_key, "confirm", "Yes — build this", payload)
          }
        >
          {busy ? <StudioBusyLabel>Generating…</StudioBusyLabel> : "Generate"}
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={busy}
          data-testid="studio-diagnosis-reject"
          onClick={() =>
            onAnswer(clarification.merge_key, "reject", "That's not what I meant")
          }
        >
          Start over
        </button>
        {installStep ? (
          <p
            id="studio-diagnosis-install-hint"
            className="clarify-actions-hint"
            data-testid="studio-diagnosis-install-hint"
          >
            {installStep.blocked_message}
          </p>
        ) : null}
        {needsHostChoice ? (
          <p id="studio-diagnosis-host-hint" className="clarify-actions-hint">
            Choose the form this belongs on to generate.
          </p>
        ) : null}
      </div>
    </section>
  );
}

export function ClarifyInterstitial({
  clarification,
  busy,
  onAnswer,
  onDismiss,
  ...props
}: ClarifyInterstitialProps) {
  const [freeText, setFreeText] = useState("");
  const mergeKey = clarification.merge_key;
  if (clarification.kind === "diagnosis" || mergeKey === "diagnosis") {
    return <DiagnosisCard
        clarification={clarification}
        busy={busy}
        onAnswer={onAnswer}
        onRetryDesign={props.onRetryDesign}
        onInstallApps={props.onInstallApps}
        connectionReadOnly={props.connectionReadOnly}
        connectionId={props.connectionId}
        isOdooOnline={props.isOdooOnline}
        odooUrl={props.odooUrl}
        sessionId={props.sessionId}
      />;
  }

  return (
    <section className="card clarify-card" data-testid="studio-clarify" aria-labelledby="studio-clarify-q">
      <h2 id="studio-clarify-q" className="clarify-question">
        {clarification.question}
      </h2>
      {clarification.help ? <p className="clarify-help">{clarification.help}</p> : null}
      {clarification.understood ? (
        <p className="clarify-help clarify-help--context" data-testid="clarify-understood">
          <strong>Here&apos;s what I understood:</strong> {clarification.understood}
        </p>
      ) : null}
      <div className="studio-chip-row">
        {(clarification.options || []).map((opt) => (
          <SuggestionChip
            key={opt.id}
            label={opt.label}
            disabled={busy}
            onClick={() => onAnswer(mergeKey, opt.id, opt.label)}
          />
        ))}
      </div>
      <textarea
        className="textarea"
        rows={2}
        aria-label="Answer in your own words"
        placeholder="Or type it in your own words…"
        value={freeText}
        onChange={(e) => setFreeText(e.target.value)}
        disabled={busy}
      />
      <div className="clarify-actions">
        <button
          type="button"
          className="btn btn-primary"
          disabled={busy || !freeText.trim()}
          onClick={() => onAnswer(mergeKey, "free_text", freeText.trim())}
        >
          {busy ? <StudioBusyLabel>Continuing…</StudioBusyLabel> : "Continue"}
        </button>
        {onDismiss && clarification.default_id ? (
          <button
            type="button"
            className="btn btn-secondary"
            disabled={busy}
            onClick={() => {
              onDismiss();
              onAnswer(mergeKey, clarification.default_id || "", "Best guess default");
            }}
          >
            Use default
          </button>
        ) : null}
      </div>
    </section>
  );
}
