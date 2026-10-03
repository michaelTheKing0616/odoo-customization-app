/** Odoo 20 folds record rules into ir.access. ≤19 keeps ir.model.access + ir.rule. */

export const ODOO20_COMBINED_ACCESS_NOTE =
  "Odoo 20 combines access rights and record rules.";

export function usesCombinedIrAccess(major: number | null | undefined): boolean {
  return typeof major === "number" && major >= 20;
}

/** Only offer an ir.rule create when the major is known and below 20. */
export function shouldOfferRecordRuleCreate(major: number | null | undefined): boolean {
  return typeof major === "number" && major < 20;
}

export function shouldFetchRecordRules(major: number | null | undefined): boolean {
  return shouldOfferRecordRuleCreate(major);
}

export type AccessScreenBranch = {
  combinedIrAccess: boolean;
  offerRecordRuleCreate: boolean;
  fetchRecordRules: boolean;
  note: string | null;
};

export function accessScreenBranch(major: number | null | undefined): AccessScreenBranch {
  const combined = usesCombinedIrAccess(major);
  const offerRule = shouldOfferRecordRuleCreate(major);
  return {
    combinedIrAccess: combined,
    offerRecordRuleCreate: offerRule,
    fetchRecordRules: offerRule,
    note: combined ? ODOO20_COMBINED_ACCESS_NOTE : null,
  };
}

/** Returns true only when the create callback ran. Major 20 never calls it. */
export function invokeRecordRuleCreate(
  major: number | null | undefined,
  create: () => void,
): boolean {
  if (!shouldOfferRecordRuleCreate(major)) return false;
  create();
  return true;
}
