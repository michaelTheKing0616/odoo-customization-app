"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";
import type { EngineNode, EngineOp, EngineViewType, FieldImpactOut, Person, PreviewAsOut, Role } from "@/lib/api/view-engine";
import { accessOps, copyRuleOps, levelsFromGroups, splitLevels, type AccessLevel } from "@/lib/viewDesigner2a";
import { nodeName, type TreeIndex } from "@/lib/viewEngineOps";
import { Note } from "../view-designer/Note";
import styles from "./ViewDesigner.module.css";
import { Term } from "@/components/ui/Term";

type Props = {
  connectionId: string;
  model: string;
  viewType: EngineViewType;
  ops: EngineOp[];
  nodes: EngineNode[];
  index: TreeIndex;
  roles: Role[];
  onOps: (ops: EngineOp[], summary: string) => void;
  onOpenRecordAccess: () => void;
  /** Odoo 17 can't limit this field to roles: open a hide rule on it instead. */
  onUseRule?: (nodeId: string) => void;
  errorText: (err: unknown) => string;
};

const LEVEL_WORDS: Record<AccessLevel, string> = { edit: "Can edit", see: "Can only see", hidden: "Hidden" };

/** Editable "Who can see it" (SPEC 15): roles, plain impact, blocks, person check. */
export function WhoCanSeePanel({ connectionId, model, viewType, ops, nodes, index, roles, onOps, onOpenRecordAccess, onUseRule, errorText }: Props) {
  const primary = nodes[0];
  const [levels, setLevels] = useState<Record<string, AccessLevel>>({});
  const [query, setQuery] = useState("");
  const [impact, setImpact] = useState<FieldImpactOut | null>(null);
  const [impactError, setImpactError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [personQuery, setPersonQuery] = useState("");
  const [people, setPeople] = useState<Person[]>([]);
  const [personResult, setPersonResult] = useState<{ person: Person; out: PreviewAsOut } | null>(null);
  const [copyFrom, setCopyFrom] = useState("");

  const nodeKey = nodes.map((n) => n.id).join("|");
  useEffect(() => {
    setLevels(levelsFromGroups(primary?.attrs.groups));
    setImpact(null);
    setPersonResult(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodeKey]);

  const roleName = useMemo(() => new Map(roles.map((r) => [r.xmlid, r.name])), [roles]);
  const chosen = Object.keys(levels);
  const changed = JSON.stringify(splitLevels(levels)) !== JSON.stringify(splitLevels(levelsFromGroups(primary?.attrs.groups)));
  const fieldsOnly = nodes.every((n) => n.tag === "field");

  // Plain impact preview, recomputed as roles change.
  useEffect(() => {
    if (!primary || !changed) {
      setImpact(null);
      setImpactError(null);
      return;
    }
    const { edit, see } = splitLevels(levels);
    let live = true;
    setChecking(true);
    const t = window.setTimeout(() => {
      api
        .fieldImpact(connectionId, { model, view_type: viewType, ops }, {
          node: primary.id, edit, see, also: nodes.slice(1).map((n) => n.id),
        })
        .then((out) => live && (setImpact(out), setImpactError(null)))
        .catch((err) => live && (setImpact(null), setImpactError(errorText(err))))
        .finally(() => live && setChecking(false));
    }, 300);
    return () => {
      live = false;
      window.clearTimeout(t);
    };
  }, [levels, changed, primary, nodes, connectionId, model, viewType, ops, errorText]);

  useEffect(() => {
    if (personQuery.trim().length < 2) {
      setPeople([]);
      return;
    }
    let live = true;
    const t = window.setTimeout(() => {
      api.people(connectionId, personQuery.trim()).then((out) => live && setPeople(out.people)).catch(() => undefined);
    }, 250);
    return () => {
      live = false;
      window.clearTimeout(t);
    };
  }, [personQuery, connectionId]);

  if (!primary) return null;
  const locked = nodes.some((n) => !n.anchor) || primary.kind === "root";
  const matches = query.trim()
    ? roles.filter((r) => !levels[r.xmlid] && r.name.toLowerCase().includes(query.trim().toLowerCase())).slice(0, 8)
    : [];
  const blocks = impact?.blocks ?? [];

  const checkPerson = async (p: Person) => {
    setPeople([]);
    setPersonQuery(p.name);
    try {
      const out = await api.previewAs(connectionId, { model, view_type: viewType, ops }, { user_id: p.id });
      setPersonResult({ person: p, out });
    } catch (err) {
      setPersonResult(null);
      setImpactError(errorText(err));
    }
  };
  const personSees = personResult ? personResult.out.visibility[primary.id] : null;

  const sameCopies = impact?.same_field_nodes?.filter((id) => !nodes.some((n) => n.id === id)) ?? [];
  const sourceChoices = [...index.byId.values()].filter(
    (n) => n.tag === "field" && n.anchor && !nodes.some((x) => x.id === n.id) && (n.attrs.groups || n.attrs.invisible || n.attrs.required || n.attrs.readonly),
  );

  return (
    <section className={styles.section} aria-labelledby="vd-who" data-testid="vd-who">
      <h3 id="vd-who" className={styles.sectionTitle}>
        Who can see it{nodes.length > 1 ? ` (${nodes.length} items)` : ""}
      </h3>
      {chosen.length === 0 ? <p className={styles.muted}>Everyone who can open this <Term tech="ir.model">record type</Term>.</p> : null}
      <ul className={styles.list}>
        {chosen.map((g) => (
          <li key={g} className={styles.listItem}>
            <span>{roleName.get(g) ?? g}</span>
            <span className={styles.row}>
              <select
                className={styles.select}
                aria-label={`What ${roleName.get(g) ?? g} can do`}
                value={levels[g]}
                disabled={locked}
                onChange={(e) => setLevels((l) => ({ ...l, [g]: e.target.value as AccessLevel }))}
              >
                {(["edit", "see"] as AccessLevel[])
                  .filter((l) => l === "edit" || fieldsOnly)
                  .map((l) => (
                    <option key={l} value={l}>{LEVEL_WORDS[l]}</option>
                  ))}
              </select>
              <Button
                size="sm"
                variant="ghost"
                aria-label={`Remove ${roleName.get(g) ?? g}`}
                disabled={locked}
                onClick={() =>
                  setLevels((l) => {
                    const next = { ...l };
                    delete next[g];
                    return next;
                  })
                }
              >
                Remove
              </Button>
            </span>
          </li>
        ))}
      </ul>
      <label className={styles.fieldLabel} htmlFor="vd-role-search">Limit to a role</label>
      <Input id="vd-role-search" value={query} disabled={locked} placeholder="Sales…" onChange={(e) => setQuery(e.target.value)} />
      {matches.length ? (
        <ul className={styles.list} aria-label="Matching roles">
          {matches.map((r) => (
            <li key={r.xmlid}>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setLevels((l) => ({ ...l, [r.xmlid]: "edit" }));
                  setQuery("");
                }}
              >
                {r.name}, {r.people === 1 ? "1 person" : `${r.people} people`}
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
      <p className={styles.muted}>Everyone not listed: {LEVEL_WORDS.hidden.toLowerCase()} once a role is listed.</p>

      {checking ? <Note tone="busy" role="status">Checking who this affects…</Note> : null}
      {impact ? (
        <div className={styles.stack} data-testid="vd-impact">
          {impact.impact.map((l) => <p key={l}>{l}</p>)}
          {impact.warnings.map((w) => <Note tone="warning" key={w}>{w}</Note>)}
          {blocks.map((b) => <Note tone="danger" key={b} role="alert">{b}</Note>)}
          {impact.alternative && onUseRule ? (
            <Button size="sm" variant="primary" data-testid="vd-use-rule" onClick={() => onUseRule(impact.alternative!.node)}>
              {impact.alternative.label}
            </Button>
          ) : null}
          {sameCopies.length ? (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onOps(accessOps([...nodes.map((n) => n.id), ...sameCopies], levels), `Changed who can see ${nodeName(primary)} in every place`)}
              disabled={blocks.length > 0}
            >
              Change every copy on this screen
            </Button>
          ) : null}
        </div>
      ) : null}
      {impactError ? <Note tone="danger" role="alert">{impactError}</Note> : null}
      <div className={styles.row}>
        <Button
          size="sm"
          variant="primary"
          disabled={locked || !changed || checking || blocks.length > 0 || !impact}
          onClick={() => onOps(accessOps(nodes.map((n) => n.id), levels), `Changed who can see ${nodes.length > 1 ? `${nodes.length} items` : nodeName(primary)}`)}
        >
          Use these roles
        </Button>
        {primary.attrs.groups ? (
          <Button size="sm" variant="ghost" disabled={locked} onClick={() => setLevels({})}>
            Everyone
          </Button>
        ) : null}
      </div>

      {sourceChoices.length ? (
        <div className={styles.row}>
          <label className={styles.fieldLabel} htmlFor="vd-copy-from">Copy rules from</label>
          <select id="vd-copy-from" className={styles.select} value={copyFrom} disabled={locked} onChange={(e) => setCopyFrom(e.target.value)}>
            <option value="">Choose a field…</option>
            {sourceChoices.map((n) => (
              <option key={n.id} value={n.id}>{nodeName(n)}</option>
            ))}
          </select>
          <Button
            size="sm"
            variant="ghost"
            disabled={!copyFrom || locked}
            onClick={() => {
              const src = index.byId.get(copyFrom);
              if (!src) return;
              onOps(copyRuleOps(src, nodes.map((n) => n.id), ops), `Copied rules from ${nodeName(src)}`);
              setCopyFrom("");
            }}
          >
            Copy
          </Button>
        </div>
      ) : null}

      <label className={styles.fieldLabel} htmlFor="vd-person">Can this person see it?</label>
      <Input id="vd-person" value={personQuery} placeholder="Type a name" onChange={(e) => setPersonQuery(e.target.value)} />
      {people.length ? (
        <ul className={styles.list} aria-label="People">
          {people.map((p) => (
            <li key={p.id}>
              <Button size="sm" variant="ghost" onClick={() => void checkPerson(p)}>{p.name}</Button>
            </li>
          ))}
        </ul>
      ) : null}
      {personResult && personSees ? (
        <p data-testid="vd-person-answer">
          {personSees.visible
            ? `Yes, ${personResult.person.name} can see ${nodeName(primary)}${personResult.out.read_only ? ", but can't change it" : ""}.`
            : `No. ${personSees.reason ?? ""}`}{" "}
          <span className={styles.muted}>{personResult.out.based_on}</span>
        </p>
      ) : null}
      <Button size="sm" variant="ghost" onClick={onOpenRecordAccess}>Access to this record type…</Button>
    </section>
  );
}
