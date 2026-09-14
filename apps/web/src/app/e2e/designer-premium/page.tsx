"use client";

import { useState } from "react";
import { DesignerFieldInspector } from "@/components/designer/DesignerFieldInspector";
import { DesignerSessionBar } from "@/components/designer/DesignerSessionBar";
import { OverlayHud } from "@/components/designer/OverlayHud";
import { OverlayStructurePicker } from "@/components/designer/OverlayStructurePicker";
import { XPathInheritPanel } from "@/components/designer/XPathInheritPanel";
import { Callout } from "@/components/ui/Callout";
import { Card, PageHeader } from "@/components/ui/layout-primitives";
import { TooltipProvider } from "@/components/ui/Tooltip";
import { fallbackWidgetsForTtype } from "@/lib/widgetCatalog";
import type { FieldRow } from "@/lib/api";

const FIELD: FieldRow = {
  id: 1,
  name: "x_name",
  field_description: "Guest",
  ttype: "char",
  required: true,
  readonly: false,
  relation: null,
  state: "manual",
  help: "Visitor display name",
};

export default function DesignerPremiumHarnessPage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const [expr, setExpr] = useState("//field[@name='x_name']");
  const [groupXpath, setGroupXpath] = useState("//group[@name='x_group_identity']");

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return (
    <TooltipProvider>
      <main className="mx-auto max-w-6xl space-y-4 p-6" data-testid="designer-premium-harness">
        <PageHeader
          title="View Designer"
          description="E2E mock · Tracks A–D chrome. Inherit save. Session undo is not Odoo rollback. Promote stays human."
        />
        <Callout variant="info" title="View-layer only">
          Removing a field from the view does not delete the database column. Completeness ≠ Cert ≠
          Autopilot.
        </Callout>
        <DesignerSessionBar
          publishState="unpublished"
          canUndo
          canRedo={false}
          canRollbackPublish
          undoLabel="move Guest"
          onUndo={() => undefined}
          onRedo={() => undefined}
          onRollbackPublish={() => undefined}
        />
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-4">
            <OverlayHud
              fieldName="x_name"
              ttype="char"
              xpath="//field[@name='x_name']"
              matchCount={1}
            />
            <OverlayStructurePicker
              label="Move into group"
              hint="Named groups survive upgrades. Positional group[2] does not."
              candidates={[
                {
                  xpath: "//group[@name='x_group_identity']",
                  tag: "group",
                  label: "Identity",
                  score: 12,
                },
                {
                  xpath: "//page[@name='x_page_notes']",
                  tag: "page",
                  label: "Notes",
                  score: 8,
                },
              ]}
              value={groupXpath}
              onChange={setGroupXpath}
            />
            <XPathInheritPanel
              expr={expr}
              position="inside"
              bodyXml={'<field name="x_host_id"/>'}
              previewArch={'<form><sheet><group name="x_group_identity"><field name="x_name"/></group></sheet></form>'}
              issues={[
                {
                  severity: "warning",
                  code: "positional",
                  message: "Named locators survive upgrades. Positional [n] does not.",
                  suggestion: "//field[@name='x_name']",
                },
              ]}
              suggestedExpr="//field[@name='x_name']"
              defaultInjectExpr="//field[@name='x_name']"
              matchCount={1}
              blocking={false}
              busy={false}
              model="x_visitor_log"
              hasOverride={false}
              onExprChange={setExpr}
              onPositionChange={() => undefined}
              onBodyChange={() => undefined}
              onPreview={() => undefined}
              onUseNamedLocator={setExpr}
              onUseAsOverride={() => undefined}
              onSave={() => undefined}
              onClearOverride={() => undefined}
            />
          </div>
          <Card className="p-4">
            <DesignerFieldInspector
              field={{
                name: "x_name",
                string: "Guest",
                required: true,
                ttype: "char",
                help: "Visitor display name",
                placeholder: "Ada Lovelace",
              }}
              fieldMeta={FIELD}
              widgetOptions={fallbackWidgetsForTtype("char")}
              widgetAdvanced={false}
              onWidgetAdvancedChange={() => undefined}
              onChange={() => undefined}
              onRemoveFromView={() => undefined}
            />
          </Card>
        </div>
      </main>
    </TooltipProvider>
  );
}
