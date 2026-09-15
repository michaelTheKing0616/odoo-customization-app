"use client";

import { createRef, useState } from "react";
import { DesignerFieldInspector } from "@/components/designer/DesignerFieldInspector";
import { DesignerLiveCanvas } from "@/components/designer/DesignerLiveCanvas";
import { DesignerSessionBar } from "@/components/designer/DesignerSessionBar";
import { DesignerStudioShell } from "@/components/designer/DesignerStudioShell";
import { DesignerToolsRail, type DesignerRailTabId } from "@/components/designer/DesignerToolsRail";
import { FieldPalette } from "@/components/designer/FieldPalette";
import { FormCanvas } from "@/components/designer/FormCanvas";
import { OverlayHud } from "@/components/designer/OverlayHud";
import { OverlayStructurePicker } from "@/components/designer/OverlayStructurePicker";
import { XPathInheritPanel } from "@/components/designer/XPathInheritPanel";
import { Callout } from "@/components/ui/Callout";
import { TooltipProvider } from "@/components/ui/Tooltip";
import { OdooPreviewScope } from "@/components/odoo-preview";
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

const PALETTE = [
  { name: "x_name", ttype: "char", label: "Guest" },
  { name: "x_host_id", ttype: "many2one", label: "Host" },
];

export default function DesignerPremiumHarnessPage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const [expr, setExpr] = useState("//field[@name='x_name']");
  const [groupXpath, setGroupXpath] = useState("//group[@name='x_group_identity']");
  const [railTab, setRailTab] = useState<DesignerRailTabId>("properties");
  const iframeRef = createRef<HTMLIFrameElement>();

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return (
    <TooltipProvider>
      <main className="min-h-screen bg-background text-ink" data-testid="designer-premium-harness">
        <DesignerStudioShell
          testId="designer-premium-studio"
          className="mx-0 mt-0 min-h-screen"
          title="View designer"
          description="E2E mock · Tracks A–D chrome. Inherit save. Session undo is not Odoo rollback. Promote stays human."
          sessionBar={
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
          }
          notices={
            <Callout variant="info" title="View-layer only">
              Removing a field from the view does not delete the database column. Completeness ≠ Cert ≠
              Autopilot.
            </Callout>
          }
          canvas={
            <DesignerLiveCanvas
              mode="structure"
              onModeChange={() => undefined}
              liveUrl={null}
              iframeRef={iframeRef}
              iframeKey={1}
              structural={
                <OdooPreviewScope showBanner>
                  <OverlayHud
                    fieldName="x_name"
                    ttype="char"
                    xpath="//field[@name='x_name']"
                    matchCount={1}
                  />
                  <div className="mt-3">
                    <FormCanvas
                      title="Visitor log"
                      groups={[
                        {
                          id: "g1",
                          string: "Identity",
                          fields: [
                            { id: "f1", name: "x_name", string: "Guest", ttype: "char", required: true },
                          ],
                        },
                      ]}
                      selectedFieldId="f1"
                      onSelectField={() => setRailTab("properties")}
                    />
                  </div>
                </OdooPreviewScope>
              }
            />
          }
          rail={
            <DesignerToolsRail
              value={railTab}
              onValueChange={setRailTab}
              tabs={[
                {
                  id: "fields",
                  label: "Fields",
                  content: <FieldPalette fields={PALETTE} />,
                },
                {
                  id: "properties",
                  label: "Properties",
                  content: (
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
                  ),
                },
                {
                  id: "structure",
                  label: "Structure",
                  content: (
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
                  ),
                },
                {
                  id: "overlay",
                  label: "Overlay",
                  content: (
                    <p className="text-xs text-muted">
                      Overlay operations attach to the live iframe when a connection is loaded.
                    </p>
                  ),
                },
                {
                  id: "advanced",
                  label: "Advanced",
                  content: (
                    <XPathInheritPanel
                      expr={expr}
                      position="inside"
                      bodyXml={'<field name="x_host_id"/>'}
                      previewArch={
                        '<form><sheet><group name="x_group_identity"><field name="x_name"/></group></sheet></form>'
                      }
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
                  ),
                },
              ]}
            />
          }
        />
      </main>
    </TooltipProvider>
  );
}
