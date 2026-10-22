"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";
import type {
  Condition,
  ConditionReading,
  ConditionRule,
  ConditionValuesOut,
  EngineField,
  EngineNode,
  EngineOp,
  RuleAttr,
} from "@/lib/api/view-engine";
import {
  LIST_OPS,
  NO_VALUE_OPS,
  RULE_WORDS,
  blankRule,
  coerceValue,
  conditionComplete,
  ruleAttrsFor,
} from "@/lib/viewDesigner2a";
import { Note } from "../view-designer/Note";
import styles from "./ViewDesigner.module.css";
import { RequiredImpact } from "./Insights2c";

const RULE_TYPES = new Set([
  "boolean", "selection", "many2one", "many2many", "one2many", "char", "text", "html",
  "integer", "float", "monetary", "date", "datetime",
]);

type Props = {
  connectionId: string;
  model: string;
  rootTag: string;
  node: EngineNode;
  fields: Record<string, EngineField>;
  onOp: (op: EngineOp) => void;
  errorText: (err: unknown) => string;
  /** Opened from "use a show/hide rule instead": start on a hide rule. */
  initialSense?: "show" | "hide";
};

/** Show and hide rules in plain words (SPEC 3.2). The server writes every sentence. */
export function RulesPanel({ connectionId, model, rootTag, node, fields, onOp, errorText, initialSense = "show" }: Props) {
  const attrs = ruleAttrsFor(node, rootTag);
  const [attr, setAttr] = useState<RuleAttr>("invisible");
  const [sense, setSense] = useState<"show" | "hide">(initialSense);
  const [text, setText] = useState("");
  const [readings, setReadings] = useState<ConditionReading[] | null>(null);
  const [unclear, setUnclear] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  const [cond, setCond] = useState<Condition>({ match: "all", rules: [] });
  const [meta, setMeta] = useState<Record<string, ConditionValuesOut>>({});
  const [sentence, setSentence] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [keep, setKeep] = useState(true);

  useEffect(() => {
    setAttr("invisible");
    setReadings(null);
    setUnclear(null);
    setCond({ match: "all", rules: [] });
    setSentence(null);
    setProblem(null);
    setText("");
  }, [node.id]);

  const fieldChoices = useMemo(
    () =>
      Object.entries(fields)
        .filter(([, f]) => RULE_TYPES.has(f.type ?? ""))
        .map(([name, f]) => ({ name, label: f.string || name }))
        .sort((a, b) => a.label.localeCompare(b.label)),
    [fields],
  );

  // Ask the server for operators and values of each field used.
  useEffect(() => {
    for (const r of cond.rules) {
      if (!r.field || meta[r.field]) continue;
      void api
        .conditionValues(connectionId, model, r.field)
        .then((out) => setMeta((m) => ({ ...m, [r.field]: out })))
        .catch(() => undefined);
    }
  }, [cond.rules, meta, connectionId, model]);

  // Code writes the sentence back for what the dropdowns say.
  useEffect(() => {
    setSentence(null);
    setProblem(null);
    if (!conditionComplete(cond)) return;
    let live = true;
    const t = window.setTimeout(() => {
      api
        .conditionCheck(connectionId, model, attr, sense, cond)
        .then((out) => live && setSentence(out.rule_sentence))
        .catch((err) => live && setProblem(errorText(err)));
    }, 250);
    return () => {
      live = false;
      window.clearTimeout(t);
    };
  }, [cond, attr, sense, connectionId, model, errorText]);

  if (!attrs.length) return null;
  const existing = node.rules?.[attr];
  const locked = !node.anchor;

  const ask = async () => {
    if (!text.trim()) return;
    setAsking(true);
    setReadings(null);
    setUnclear(null);
    try {
      const out = await api.conditionWords(connectionId, model, attr, text.trim());
      setReadings(out.readings);
      setUnclear(out.unclear);
    } catch (err) {
      setUnclear(errorText(err));
    } finally {
      setAsking(false);
    }
  };

  const updateRule = (i: number, patch: Partial<ConditionRule>) =>
    setCond((c) => ({ ...c, rules: c.rules.map((r, j) => (j === i ? { ...r, ...patch } : r)) }));

  const apply = (c: Condition, s: "show" | "hide") =>
    onOp({ op: "set_condition", node: node.id, attr, sense: s, condition: c, keep_existing: Boolean(existing) && keep });

  return (
    <section className={styles.section} aria-labelledby="vd-rules" data-testid="vd-rules">
      <h3 id="vd-rules" className={styles.sectionTitle}>Show and hide</h3>
      {attrs.length > 1 ? (
        <div className={styles.row} role="group" aria-label="Which rule">
          {attrs.map((a) => (
            <Button key={a} size="sm" variant="ghost" aria-pressed={attr === a} onClick={() => setAttr(a)}>
              {RULE_WORDS[a].label}
            </Button>
          ))}
        </div>
      ) : null}
      <p className={styles.muted} data-testid="vd-rule-now">
        {existing ? `Now: ${existing}` : "No rule yet. It follows the settings above."}
      </p>

      <form
        className={styles.stack}
        onSubmit={(e) => {
          e.preventDefault();
          void ask();
        }}
      >
        <label className={styles.fieldLabel} htmlFor="vd-rule-words">Describe it</label>
        <Input
          id="vd-rule-words"
          value={text}
          maxLength={300}
          disabled={locked}
          placeholder="Show when Stage is Won"
          onChange={(e) => setText(e.target.value)}
        />
        <Button size="sm" type="submit" loading={asking} disabled={locked || !text.trim()}>
          {asking ? "Reading…" : "Turn into a rule"}
        </Button>
      </form>
      {unclear ? <Note tone="warning" role="note">{unclear}</Note> : null}
      {readings?.length ? (
        <ul className={styles.list} aria-label="Possible readings">
          {readings.map((r) => (
            <li key={r.expression + r.sense} className={styles.listItem}>
              <span>{r.rule_sentence}</span>
              <Button size="sm" onClick={() => apply(r.condition, r.sense)}>Use this</Button>
            </li>
          ))}
        </ul>
      ) : null}

      <fieldset className={styles.stack} disabled={locked}>
        <legend className={styles.fieldLabel}>Or build it</legend>
        <div className={styles.row}>
          <select className={styles.select} aria-label="Show or hide" value={sense} onChange={(e) => setSense(e.target.value as "show" | "hide")}>
            <option value="show">{RULE_WORDS[attr].show}</option>
            <option value="hide">{RULE_WORDS[attr].hide}</option>
          </select>
          {cond.rules.length > 1 ? (
            <select
              className={styles.select}
              aria-label="Match"
              value={cond.match}
              onChange={(e) => setCond((c) => ({ ...c, match: e.target.value as "all" | "any" }))}
            >
              <option value="all">all of these are true</option>
              <option value="any">any of these is true</option>
            </select>
          ) : null}
        </div>
        {cond.rules.map((r, i) => {
          const m = meta[r.field];
          const ftype = fields[r.field]?.type;
          return (
            <div key={i} className={styles.row} data-testid="vd-rule-row">
              <select
                className={styles.select}
                aria-label="Field"
                value={r.field}
                onChange={(e) => updateRule(i, { field: e.target.value, op: "", value: undefined })}
              >
                {fieldChoices.map((f) => (
                  <option key={f.name} value={f.name}>{f.label}</option>
                ))}
              </select>
              <select
                className={styles.select}
                aria-label="Condition"
                value={r.op}
                onChange={(e) => updateRule(i, { op: e.target.value, value: LIST_OPS.has(e.target.value) ? [] : undefined })}
              >
                <option value="" disabled>Choose…</option>
                {(m?.ops ?? []).map((o) => (
                  <option key={o.op} value={o.op}>{o.label}</option>
                ))}
              </select>
              {r.op && !NO_VALUE_OPS.has(r.op) ? (
                m?.values ? (
                  <select
                    className={styles.select}
                    aria-label="Value"
                    multiple={LIST_OPS.has(r.op)}
                    value={LIST_OPS.has(r.op) ? ((r.value as Array<string | number>) ?? []).map(String) : String(r.value ?? "")}
                    onChange={(e) => {
                      const picked = Array.from(e.target.selectedOptions).map((o) => coerceValue(ftype, o.value));
                      updateRule(i, { value: LIST_OPS.has(r.op) ? picked : picked[0] });
                    }}
                  >
                    {!LIST_OPS.has(r.op) ? <option value="">Choose…</option> : null}
                    {m.values.map((v) => (
                      <option key={String(v.value)} value={String(v.value)}>{v.label}</option>
                    ))}
                  </select>
                ) : (
                  <Input
                    aria-label="Value"
                    value={String(r.value ?? "")}
                    onChange={(e) => updateRule(i, { value: coerceValue(ftype, e.target.value) })}
                  />
                )
              ) : null}
              <Button size="sm" variant="ghost" aria-label="Remove this part" onClick={() => setCond((c) => ({ ...c, rules: c.rules.filter((_, j) => j !== i) }))}>
                Remove
              </Button>
            </div>
          );
        })}
        <Button
          size="sm"
          variant="ghost"
          disabled={!fieldChoices.length || cond.rules.length >= 6}
          onClick={() => setCond((c) => ({ ...c, rules: [...c.rules, blankRule(fieldChoices[0]?.name ?? "", "")] }))}
        >
          Add a condition
        </Button>
        {sentence ? <p data-testid="vd-rule-sentence">{sentence}</p> : null}
        {sentence && attr === "required" && node.tag === "field" && node.name ? (
          <RequiredImpact connectionId={connectionId} model={model} field={node.name} condition={cond} inverted={sense === "hide"} errorText={errorText} />
        ) : null}
        {problem ? <Note tone="danger" role="alert">{problem}</Note> : null}
        {existing ? (
          <label className={styles.check}>
            <input type="checkbox" checked={keep} onChange={(e) => setKeep(e.target.checked)} />
            Keep Odoo&apos;s own rule too
          </label>
        ) : null}
        <div className={styles.row}>
          <Button size="sm" variant="primary" disabled={!sentence} onClick={() => apply(cond, sense)}>
            Use this rule
          </Button>
          {existing ? (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onOp({ op: "set_condition", node: node.id, attr, sense: "show", condition: null, keep_existing: false })}
            >
              Remove the rule
            </Button>
          ) : null}
        </div>
      </fieldset>
    </section>
  );
}
