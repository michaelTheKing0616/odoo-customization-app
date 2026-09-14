/** User-visible labels for Expert caution flags (server-computed only). */

export type ExpertCautionTone = "warning" | "info" | "danger";

const LABELS: Record<string, string> = {
  legal_tax_deflection: "Not legal or tax advice",
  low_retrieval: "Limited source matches",
  pcm_consistent_refusal: "Protected module policy",
  instance_caveats: "Instance-specific caveats",
  rule_based_diagnosis: "Rule-based fix",
  rule_based_stack_guidance: "Curated module stack",
  inferred_stack: "Stack inferred from your question",
  access: "Access / ACL",
};

const DESCRIPTIONS: Record<string, string> = {
  legal_tax_deflection:
    "This is operational guidance, not legal, tax, or accounting advice.",
  low_retrieval:
    "Few knowledge matches — treat the answer as a starting point, not a spec.",
  pcm_consistent_refusal:
    "Protected Community modules stay read/link-only. Expert will not suggest mutating them.",
  instance_caveats:
    "This connection may differ from docs. Confirm on the live instance before you write.",
  rule_based_diagnosis:
    "A deterministic rule matched this error. Still verify ACL and the model on this database.",
  rule_based_stack_guidance:
    "Suggested apps come from a curated stack, not from installing or promoting anything.",
  inferred_stack:
    "The module list is inferred from your question. Expert does not auto-install or auto-promote.",
  access:
    "Usually missing ir.model.access or a record rule — not a cue to bypass security.",
};

export function formatExpertCautionFlag(flag: string): string | null {
  if (!flag.trim()) return null;
  if (flag.startsWith("protected_")) {
    const model = flag.split(":").slice(1).join(":");
    return model ? `Protected: ${model}` : "Protected ERP area";
  }
  if (LABELS[flag]) return LABELS[flag];
  if (flag.startsWith("rule_based_")) return "Guidance note";
  return humanizeExpertFlag(flag);
}

export function expertCautionDescription(flag: string): string | null {
  if (flag.startsWith("protected_")) {
    const model = flag.split(":").slice(1).join(":");
    return model
      ? `${model} is a protected ERP area. Expert will not recommend mutating it.`
      : "This touches a protected ERP area. Expert will not recommend mutating it.";
  }
  if (DESCRIPTIONS[flag]) return DESCRIPTIONS[flag];
  if (flag.startsWith("rule_based_")) {
    return "Guidance from a deterministic rule. Completeness ≠ Cert ≠ Autopilot.";
  }
  return null;
}

export function expertCautionTone(flag: string): ExpertCautionTone {
  if (flag.startsWith("protected_") || flag === "pcm_consistent_refusal") return "danger";
  if (flag === "legal_tax_deflection" || flag === "access") return "warning";
  return "warning";
}

function humanizeExpertFlag(flag: string): string {
  return flag
    .split(/[_:]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
