"use client";

import { useEffect, useMemo, useState } from "react";
import type { StudioClarification, StudioUnderstanding } from "@/lib/studio-session";
import { SuggestionChip } from "./SuggestionChip";
import { StudioBusyLabel } from "./StudioBusyLabel";

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

function DiagnosisCard({
  clarification,
  busy,
  onAnswer,
}: {
  clarification: StudioClarification;
  busy?: boolean;
  onAnswer: ClarifyInterstitialProps["onAnswer"];
}) {
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

  useEffect(() => {
    const next = clarification.understanding || {};
    setTitle(next.title || "");
    setHostModel(next.host_model || "");
    setInheritExisting(Boolean(next.inherit_existing));
    setNeedsModule(Boolean(next.needs_module));
    setConstraints(Array.isArray(next.constraints) ? next.constraints : []);
    setOperatorNote("");
    setNewConstraint("");
  }, [clarification.understanding]);

  const payload: DiagnosisPayload = useMemo(
    () => ({
      title: title.trim(),
      host_model: inheritExisting ? hostModel || null : null,
      inherit_existing: inheritExisting,
      needs_module: goldLocked ? true : needsModule,
      constraints,
      gold_artifact_id: seed.gold_artifact_id,
      operator_note: operatorNote.trim() || undefined,
    }),
    [
      constraints,
      goldLocked,
      hostModel,
      inheritExisting,
      needsModule,
      operatorNote,
      seed.gold_artifact_id,
      title,
    ],
  );

  function addConstraint() {
    const row = newConstraint.trim();
    if (!row) return;
    setConstraints((prev) => (prev.includes(row) ? prev : [...prev, row].slice(0, 12)));
    setNewConstraint("");
  }

  return (
    <div className="card clarify-card" data-testid="studio-diagnosis">
      <p className="clarify-kicker">Diagnosis — edit if this is wrong</p>
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
            className="input"
            style={{ marginTop: 8 }}
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
          <p className="clarify-help" style={{ marginTop: 8 }}>
            A new kind of record on the home screen.
          </p>
        )}
      </div>
      <div className="diagnosis-field">
        <span>How it is delivered</span>
        <div className="studio-chip-row">
          <SuggestionChip
            label="Option A module"
            selected={needsModule}
            disabled={busy || goldLocked}
            onClick={() => setNeedsModule(true)}
          />
          <SuggestionChip
            label="Live fields only"
            selected={!needsModule}
            disabled={busy || goldLocked}
            onClick={() => setNeedsModule(false)}
          />
        </div>
        {goldLocked ? (
          <p className="clarify-help" style={{ marginTop: 8 }}>
            Gold template {seed.gold_artifact_id} stays a module — zip → sandbox → Promote.
          </p>
        ) : needsModule ? (
          <p className="clarify-help" style={{ marginTop: 8 }}>
            Python/QWeb — not Install this app.
          </p>
        ) : inheritExisting ? (
          <p className="clarify-help" style={{ marginTop: 8 }}>
            Metadata on the form people already use.
          </p>
        ) : (
          <p className="clarify-help" style={{ marginTop: 8 }}>
            Live metadata for a new home-screen app tile — not an inherit on Employees.
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
        <div className="chat-input-row" style={{ marginTop: 8 }}>
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
      <label className="diagnosis-field">
        <span>Anything to correct</span>
        <textarea
          className="textarea"
          rows={2}
          disabled={busy}
          placeholder="e.g. inherit purchase.order, not Sales — WHT is 5%"
          value={operatorNote}
          onChange={(e) => setOperatorNote(e.target.value)}
        />
      </label>
      <div className="studio-chip-row" style={{ marginTop: 16 }}>
        <button
          type="button"
          className="btn btn-brand btn-sm"
          disabled={busy || (inheritExisting && !goldLocked && !hostModel)}
          data-testid="studio-diagnosis-confirm"
          onClick={() =>
            onAnswer(clarification.merge_key, "confirm", "Yes — build this", payload)
          }
        >
          {busy ? <StudioBusyLabel>Building…</StudioBusyLabel> : "Yes — build this"}
        </button>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          disabled={busy}
          data-testid="studio-diagnosis-reject"
          onClick={() =>
            onAnswer(clarification.merge_key, "reject", "That's not what I meant")
          }
        >
          Start over
        </button>
      </div>
    </div>
  );
}

export function ClarifyInterstitial({
  clarification,
  busy,
  onAnswer,
  onDismiss,
}: ClarifyInterstitialProps) {
  const [freeText, setFreeText] = useState("");
  const mergeKey = clarification.merge_key;
  if (clarification.kind === "diagnosis" || mergeKey === "diagnosis") {
    return <DiagnosisCard clarification={clarification} busy={busy} onAnswer={onAnswer} />;
  }

  return (
    <div className="card clarify-card" data-testid="studio-clarify">
      <p className="clarify-kicker">One quick check</p>
      <p className="clarify-question">{clarification.question}</p>
      {clarification.help ? <p className="clarify-help">{clarification.help}</p> : null}
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
        placeholder="Or type it in your own words…"
        value={freeText}
        onChange={(e) => setFreeText(e.target.value)}
        disabled={busy}
      />
      <div className="studio-chip-row" style={{ marginTop: 12 }}>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          disabled={busy || !freeText.trim()}
          onClick={() => onAnswer(mergeKey, "free_text", freeText.trim())}
        >
          {busy ? <StudioBusyLabel>Continuing…</StudioBusyLabel> : "Continue"}
        </button>
        {onDismiss && clarification.default_id ? (
          <button
            type="button"
            className="btn btn-secondary btn-sm"
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
    </div>
  );
}
