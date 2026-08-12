/** User-visible labels for Expert caution flags (server-computed only). */
export function formatExpertCautionFlag(flag: string): string | null {
  if (flag.startsWith("protected_")) {
    const model = flag.split(":").slice(1).join(":");
    return model ? `Protected: ${model}` : "Protected ERP area";
  }
  if (flag === "legal_tax_deflection") return "Not legal or tax advice";
  if (flag === "low_retrieval") return "Limited source matches";
  if (flag === "pcm_consistent_refusal") return "Protected module policy";
  if (flag === "instance_caveats") return "Instance-specific caveats";
  if (flag === "rule_based_diagnosis") return "Rule-based fix";
  if (flag === "rule_based_stack_guidance") return "Curated module stack";
  if (flag === "inferred_stack") return "Stack inferred from your question";
  if (flag.startsWith("rule_based_")) return "Guidance note";
  return null;
}
