"use client";

import { useMemo, useState } from "react";
import { ModuleSpecEditor } from "@/components/ModuleSpecEditor";
import { ModuleSpecApplyBar } from "@/components/modulespec/ModuleSpecApplyBar";
import { ModuleSpecHandoffBar } from "@/components/modulespec/ModuleSpecHandoffBar";
import { ModuleSpecHonestyBanners } from "@/components/modulespec/ModuleSpecHonestyBanners";
import { ModuleSpecIdentityCard } from "@/components/modulespec/ModuleSpecIdentityCard";
import { ModuleSpecReadiness } from "@/components/modulespec/ModuleSpecReadiness";
import { ModuleSpecSessionBar } from "@/components/modulespec/ModuleSpecSessionBar";
import { ModuleSpecShell } from "@/components/modulespec/ModuleSpecShell";
import {
  cloneModuleSpec,
  type ModuleSpecDoc,
} from "@/lib/modulespec-types";
import {
  isSpecDirty,
  localReadiness,
  moduleSpecJourneyFromState,
  moduleSpecSessionState,
  sessionSubmitHint,
} from "@/lib/modulespec-journey";
import "@/styles/studio-refinement.css";

const SAMPLE: ModuleSpecDoc = {
  technical_name: "visitor_log",
  display_name: "Visitor log",
  depends: ["base", "mail"],
  models: [
    {
      model: "x_visitor_log",
      description: "Visitor log",
      mode: "new",
      fields: [
        { name: "x_name", ttype: "char", string: "Guest", required: true },
        { name: "x_host_id", ttype: "many2one", string: "Host", relation: "res.users" },
        { name: "x_checked_in", ttype: "datetime", string: "Checked in" },
      ],
    },
  ],
  views: [
    {
      name: "x_visitor_log.form",
      model: "x_visitor_log",
      type: "form",
      mode: "primary",
      arch: "<form><sheet><group><field name=\"x_name\"/></group></sheet></form>",
    },
  ],
  menus: [{ name: "Visitor log", technical_name: "menu_x_visitor_log", sequence: 10 }],
  access_rules: [
    {
      name: "Visitor log user",
      model: "model_x_visitor_log",
      group: "base.group_user",
      perm_read: 1,
      perm_write: 1,
      perm_create: 1,
      perm_unlink: 0,
    },
  ],
  _scorecard: { score_0_10: 8.5 },
};

export default function ModuleSpecE2ePage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const [spec, setSpec] = useState<ModuleSpecDoc>(SAMPLE);
  const [baseline] = useState<ModuleSpecDoc>(() => cloneModuleSpec(SAMPLE));
  const dirty = isSpecDirty(spec, baseline);
  const sessionState = moduleSpecSessionState({ dirty, savedOnce: true });
  const readiness = useMemo(() => localReadiness(spec), [spec]);
  const journey = moduleSpecJourneyFromState({
    hydrated: true,
    hasContent: true,
    hasLiveValidation: false,
  });

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return (
    <ModuleSpecShell connectionId="e2e-mock" connectionName="E2E mock" journey={journey}>
      <ModuleSpecHonestyBanners completenessNote="Completeness 8.5/10 is ModuleSpec hygiene, not go-live." />
      <ModuleSpecSessionBar
        sessionState={sessionState}
        canDiscard={dirty}
        submitLabel={sessionSubmitHint({ sessionState })}
        onDiscard={() => setSpec(cloneModuleSpec(baseline))}
      />
      <ModuleSpecApplyBar
        busy={null}
        canSave
        canApply={!readiness.applyBlocked}
        canValidate
        hasModels
        hasContent
        stockReuse={false}
        onImportFile={() => undefined}
        onSaveProject={() => undefined}
        onGenerateUi={() => undefined}
        onDownloadZip={() => undefined}
      />
      <ModuleSpecIdentityCard value={spec} barcodeModuleAllowed onChange={setSpec} />
      <ModuleSpecReadiness report={readiness} canValidate onValidate={() => undefined} />
      <ModuleSpecEditor
        value={spec}
        onChange={setSpec}
        designerHref="/connections/e2e-mock/designer?model=x_visitor_log"
      />
      <ModuleSpecHandoffBar
        connectionId="e2e-mock"
        designerHref="/connections/e2e-mock/designer?model=x_visitor_log"
        designerModel="x_visitor_log"
      />
    </ModuleSpecShell>
  );
}
