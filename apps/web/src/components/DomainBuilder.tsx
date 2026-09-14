"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

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

const CONTROL_CLASS =
  "h-9 rounded-md border border-border-subtle bg-surface px-2.5 text-sm text-ink outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2";

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

export function validateDomainString(domain: string): { ok: boolean; message: string | null } {
  const trimmed = domain.trim();
  if (!trimmed || trimmed === "[]") return { ok: true, message: null };

  const opens = (trimmed.match(/\[/g) || []).length;
  const closes = (trimmed.match(/\]/g) || []).length;
  if (opens !== closes) {
    return { ok: false, message: "Unbalanced brackets in this domain." };
  }

  const rules = parseDomainString(trimmed);
  const usable = rules.filter((r) => r.field.trim());
  if (!usable.length) {
    return {
      ok: false,
      message: "Could not parse this domain. Add a field, operator, and value, or edit raw.",
    };
  }
  return { ok: true, message: null };
}

type Props = {
  value: string;
  onChange: (domain: string) => void;
  label?: string;
  hint?: string;
  className?: string;
};

export function DomainBuilder({ value, onChange, label, hint, className }: Props) {
  const [rules, setRules] = useState<DomainRule[]>(() => parseDomainString(value));
  const [showRaw, setShowRaw] = useState(false);

  useEffect(() => {
    setRules(parseDomainString(value));
  }, [value]);

  const serialized = domainRulesToString(rules);
  const validation = useMemo(() => validateDomainString(value), [value]);

  function commit(next: DomainRule[]) {
    setRules(next);
    onChange(domainRulesToString(next));
  }

  function updateRule(index: number, patch: Partial<DomainRule>) {
    commit(rules.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  }

  return (
    <div className={className ?? "space-y-2"} data-testid="domain-builder">
      {label ? (
        <span className="block text-sm font-medium text-ink">{label}</span>
      ) : null}
      {hint ? <p className="text-xs text-muted">{hint}</p> : null}
      <p className="text-xs text-muted">
        Apply when all of these match →{" "}
        <code className="rounded-sm bg-surface-muted px-1 py-0.5 text-[11px] text-ink">
          {serialized}
        </code>
      </p>
      {rules.map((rule, i) => (
        <div key={i} className="flex flex-wrap items-center gap-2">
          <input
            value={rule.field}
            onChange={(e) => updateRule(i, { field: e.target.value })}
            placeholder="Field"
            aria-label={`Domain field ${i + 1}`}
            className={cn(CONTROL_CLASS, "min-w-[8rem] flex-1 font-mono")}
          />
          <select
            value={rule.op}
            onChange={(e) => updateRule(i, { op: e.target.value as DomainOp })}
            aria-label={`Domain operator ${i + 1}`}
            className={cn(CONTROL_CLASS, "w-[5.5rem]")}
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
            placeholder="Value"
            aria-label={`Domain value ${i + 1}`}
            className={cn(CONTROL_CLASS, "min-w-[8rem] flex-1 font-mono")}
          />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              const next = rules.filter((_, j) => j !== i);
              commit(next.length ? next : [{ field: "", op: "=", value: "" }]);
            }}
          >
            Remove
          </Button>
        </div>
      ))}
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => commit([...rules, { field: "", op: "=", value: "" }])}
        >
          Add condition
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => setShowRaw((s) => !s)}>
          {showRaw ? "Hide raw" : "Edit raw"}
        </Button>
      </div>
      {showRaw ? (
        <input
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            setRules(parseDomainString(e.target.value));
          }}
          aria-label="Raw domain"
          className={cn(CONTROL_CLASS, "w-full font-mono")}
        />
      ) : null}
      {validation.ok ? (
        value.trim() && value.trim() !== "[]" ? (
          <p className="text-xs text-success-strong" data-testid="domain-builder-ok">
            Domain looks valid.
          </p>
        ) : (
          <p className="text-xs text-muted" data-testid="domain-builder-empty">
            Leave empty to apply on every matching trigger.
          </p>
        )
      ) : (
        <p className="text-xs text-danger" data-testid="domain-builder-error">
          {validation.message}
        </p>
      )}
    </div>
  );
}
