import type { LiveSnapshot } from "@/lib/api";

export type Gate = { allowed: boolean; reason: string };

const FALLBACK = "Your Odoo plan or hosting doesn't allow this change.";

/** Tier gate from the same can_change data the Overview shows. Unknown keys stay locked. */
export function gate(snap: LiveSnapshot, ...keys: string[]): Gate {
  const rows = snap.can_change.filter((c) => keys.includes(c.key));
  const open = rows.find((c) => c.available === "yes");
  if (open) return { allowed: true, reason: "" };
  const reason = rows.map((c) => c.reason).find(Boolean);
  return { allowed: false, reason: reason || (rows.length ? FALLBACK : "We couldn't confirm this is allowed here yet. Run a connection check.") };
}

export function slug(label: string): string {
  return label.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 50);
}

/** "value: Label" lines -> selection pairs. A bare line uses its slug as the value. */
export function parseOptions(text: string): { value: string; label: string }[] {
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => {
      const i = l.indexOf(":");
      const label = (i >= 0 ? l.slice(i + 1) : l).trim();
      const value = (i >= 0 ? l.slice(0, i) : slug(l)).trim();
      return { value, label: label || value };
    });
}

/** Odoo's selection literal for ir.model.fields.selection (single quotes escaped). */
export function selectionLiteral(opts: { value: string; label: string }[]): string {
  const q = (s: string) => `'${s.replace(/\\/g, "\\\\").replace(/'/g, "\\'")}'`;
  return `[${opts.map((o) => `(${q(o.value)}, ${q(o.label)})`).join(", ")}]`;
}
