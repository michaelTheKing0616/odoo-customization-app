"use client";

import { useState } from "react";

export type DomainOp =
  | "="
  | "!="
  | ">"
  | ">="
  | "<"
  | "<="
  | "like"
  | "ilike"
  | "in"
  | "not in"
  | "=?"
  | "child_of";

export type DomainRule = {
  field: string;
  op: DomainOp;
  value: string;
};

const OPS: DomainOp[] = [
  "=",
  "!=",
  ">",
  ">=",
  "<",
  "<=",
  "like",
  "ilike",
  "in",
  "not in",
  "=?",
  "child_of",
];

function parseLiteral(raw: string): unknown {
  const t = raw.trim();
  if (t === "") return "";
  if (t === "True" || t === "true") return true;
  if (t === "False" || t === "false") return false;
  if (t === "None" || t === "null") return false;
  if (/^-?\d+$/.test(t)) return Number(t);
  if (/^-?\d+\.\d+$/.test(t)) return Number(t);
  if ((t.startsWith("[") && t.endsWith("]")) || (t.startsWith("(") && t.endsWith(")"))) {
    try {
      return JSON.parse(t.replace(/'/g, '"'));
    } catch {
      /* fall through */
    }
  }
  if (
    (t.startsWith("'") && t.endsWith("'")) ||
    (t.startsWith('"') && t.endsWith('"'))
  ) {
    return t.slice(1, -1);
  }
  // Preserve Odoo expressions like user.id / company_ids
  if (/^[A-Za-z_][\w.]*$/.test(t) && t.includes(".")) {
    return { __expr: t };
  }
  return t;
}

/** Serialize AND rules to an Odoo domain string. */
export function domainRulesToString(rules: DomainRule[]): string {
  const usable = rules.filter((r) => r.field.trim());
  if (!usable.length) return "[]";
  const tuples = usable.map((r) => {
    const lit = parseLiteral(r.value);
    let valueRepr: string;
    if (lit && typeof lit === "object" && "__expr" in lit) {
      valueRepr = String((lit as { __expr: string }).__expr);
    } else if (typeof lit === "string") {
      valueRepr = JSON.stringify(lit);
    } else if (typeof lit === "boolean") {
      valueRepr = lit ? "True" : "False";
    } else {
      valueRepr = JSON.stringify(lit);
    }
    return `(${JSON.stringify(r.field.trim())}, ${JSON.stringify(r.op)}, ${valueRepr})`;
  });
  return "[" + tuples.join(", ") + "]";
}

/** Best-effort parse of simple AND domain `[('a','=',1), …]`. */
export function parseDomainString(domain: string): DomainRule[] {
  const trimmed = domain.trim();
  if (!trimmed || trimmed === "[]") return [{ field: "", op: "=", value: "" }];
  const rows: DomainRule[] = [];
  const re =
    /\(\s*['"]([^'"]+)['"]\s*,\s*['"]([^'"]+)['"]\s*,\s*([^)]+?)\s*\)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(trimmed))) {
    let value = m[3].trim();
    if (
      (value.startsWith("'") && value.endsWith("'")) ||
      (value.startsWith('"') && value.endsWith('"'))
    ) {
      value = value.slice(1, -1);
    }
    rows.push({
      field: m[1],
      op: (OPS.includes(m[2] as DomainOp) ? m[2] : "=") as DomainOp,
      value,
    });
  }
  return rows.length ? rows : [{ field: "", op: "=", value: "" }];
}

type Props = {
  value: string;
  onChange: (domain: string) => void;
  label?: string;
  className?: string;
};

export function DomainBuilder({ value, onChange, label, className }: Props) {
  const [rules, setRules] = useState<DomainRule[]>(() => parseDomainString(value));
  const [showRaw, setShowRaw] = useState(false);

  function commit(next: DomainRule[]) {
    setRules(next);
    onChange(domainRulesToString(next));
  }

  function updateRule(index: number, patch: Partial<DomainRule>) {
    commit(rules.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  }

  return (
    <div className={className ?? "space-y-2"}>
      {label && <span className="text-sm text-[#a8909e]">{label}</span>}
      <p className="text-xs text-muted">
        Simple AND domain →{" "}
        <code className="text-muted">{domainRulesToString(rules)}</code>
      </p>
      {rules.map((rule, i) => (
        <div key={i} className="flex flex-wrap items-center gap-2">
          <input
            value={rule.field}
            onChange={(e) => updateRule(i, { field: e.target.value })}
            placeholder="field"
            className="min-w-[8rem] flex-1 border border-border-subtle bg-surface px-2 py-1.5 font-mono text-sm"
          />
          <select
            value={rule.op}
            onChange={(e) => updateRule(i, { op: e.target.value as DomainOp })}
            className="border border-border-subtle bg-surface px-2 py-1.5 text-sm"
          >
            {OPS.map((op) => (
              <option key={op} value={op}>
                {op}
              </option>
            ))}
          </select>
          <input
            value={rule.value}
            onChange={(e) => updateRule(i, { value: e.target.value })}
            placeholder="value"
            className="min-w-[8rem] flex-1 border border-border-subtle bg-surface px-2 py-1.5 font-mono text-sm"
          />
          <button
            type="button"
            onClick={() => {
              const next = rules.filter((_, j) => j !== i);
              commit(next.length ? next : [{ field: "", op: "=", value: "" }]);
            }}
            className="text-xs text-danger hover:underline"
          >
            Remove
          </button>
        </div>
      ))}
      <div className="flex flex-wrap gap-3 text-xs">
        <button
          type="button"
          onClick={() => commit([...rules, { field: "", op: "=", value: "" }])}
          className="text-muted hover:underline"
        >
          + Add rule
        </button>
        <button
          type="button"
          onClick={() => setShowRaw((s) => !s)}
          className="text-muted hover:underline"
        >
          {showRaw ? "Hide raw" : "Edit raw"}
        </button>
      </div>
      {showRaw && (
        <input
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            setRules(parseDomainString(e.target.value));
          }}
          className="w-full border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
        />
      )}
    </div>
  );
}
