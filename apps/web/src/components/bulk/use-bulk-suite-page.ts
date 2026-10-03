"use client";

import type { BulkRecipe } from "./bulk-helpers";
import { useBulkSuiteAccess } from "./use-bulk-suite-access";
import { useBulkSuiteRuns } from "./use-bulk-suite-runs";
import { useBulkSuiteState } from "./use-bulk-suite-state";

export function useBulkSuitePage(connectionId: string) {
  const s = useBulkSuiteState(connectionId);
  const runs = useBulkSuiteRuns(s);
  const access = useBulkSuiteAccess(s);

  function applyRecipe(r: BulkRecipe) {
    s.setModel(r.model);
    if ("domain" in r && r.domain) s.setDomainText(r.domain);
    if (r.op === "mass_edit" && "values" in r) s.setValuesText(r.values);
    s.setNotice(`Recipe loaded: ${r.label}`);
  }

  return {
    ...s,
    ...runs,
    ...access,
    applyRecipe,
  };
}

export type BulkSuitePageModel = ReturnType<typeof useBulkSuitePage>;
