"use client";

import type { Dispatch, ReactNode, RefObject, SetStateAction } from "react";
import { FieldPalette } from "@/components/designer/FieldPalette";
import {
  NicheWidgetPalette,
  type ColorPaletteEntry,
  type NicheWidgetEntry,
} from "@/components/designer/NicheWidgetPalette";
import { OverlayEditor } from "@/components/designer/OverlayEditor";
import {
  XPathInheritPanel,
  type LocatorIssue,
  type XPathPosition,
} from "@/components/designer/XPathInheritPanel";
import {
  DesignerToolsRail,
  type DesignerRailTabId,
} from "@/components/designer/DesignerToolsRail";
import type { FieldRow } from "@/lib/api";
import type { FormChild, ViewType } from "@/components/designer/designer-model";

export type DesignerStudioRailProps = {
  railTab: DesignerRailTabId;
  setRailTab: (v: DesignerRailTabId) => void;
  viewType: ViewType;
  fields: FieldRow[];
  setDragField: (name: string | null) => void;
  nicheWidgets: NicheWidgetEntry[];
  colorPalette: ColorPaletteEntry[];
  addNicheWidget: (w: NicheWidgetEntry) => void | Promise<void>;
  fieldInspector: ReactNode;
  formChildren: FormChild[];
  addGroup: () => void;
  addNotebook: () => void;
  proxyPreviewUrl: string | null;
  previewIframeRef: RefObject<HTMLIFrameElement | null>;
  connectionId: string;
  model: string;
  setLastSnapshotId: Dispatch<SetStateAction<string | null>>;
  setPreviewKey: Dispatch<SetStateAction<number>>;
  setNotice: (v: string | null) => void;
  refreshSnapshots: () => void | Promise<void>;
  xpathExpr: string;
  xpathPosition: XPathPosition;
  xpathBody: string;
  xpathArchPreview: string;
  xpathIssues: LocatorIssue[];
  xpathSuggested: string | null;
  xpathDefaultInject: string | null;
  xpathMatchCount: number | null;
  xpathBlocking: boolean;
  busy: boolean;
  archOverride: string | null;
  setXpathExpr: Dispatch<SetStateAction<string>>;
  setXpathBlocking: (v: boolean) => void;
  setXpathPosition: (v: XPathPosition) => void;
  setXpathBody: (v: string) => void;
  runXpathPreview: () => void | Promise<unknown>;
  setArch: (v: string) => void;
  setArchOverride: (v: string | null) => void;
  onSaveXpathInherit: () => void | Promise<unknown>;
};

export function DesignerStudioRail(props: DesignerStudioRailProps) {
  const {
    railTab,
    setRailTab,
    viewType,
    fields,
    setDragField,
    nicheWidgets,
    colorPalette,
    addNicheWidget,
    fieldInspector,
    formChildren,
    addGroup,
    addNotebook,
    proxyPreviewUrl,
    previewIframeRef,
    connectionId,
    model,
    setLastSnapshotId,
    setPreviewKey,
    setNotice,
    refreshSnapshots,
    xpathExpr,
    xpathPosition,
    xpathBody,
    xpathArchPreview,
    xpathIssues,
    xpathSuggested,
    xpathDefaultInject,
    xpathMatchCount,
    xpathBlocking,
    busy,
    archOverride,
    setXpathExpr,
    setXpathBlocking,
    setXpathPosition,
    setXpathBody,
    runXpathPreview,
    setArch,
    setArchOverride,
    onSaveXpathInherit,
  } = props;

  return (
    <DesignerToolsRail
      value={railTab}
      onValueChange={setRailTab}
      tabs={[
        {
          id: "fields",
          label: "Fields",
          content: (
            <div className="space-y-3">
              <FieldPalette
                fields={fields.map((f) => ({
                  name: f.name,
                  ttype: f.ttype,
                  label: f.field_description || undefined,
                }))}
                onDragStart={(name) => setDragField(name)}
              />
              {(viewType === "form" || viewType === "kanban") && (
                <NicheWidgetPalette
                  widgets={nicheWidgets}
                  colorPalette={colorPalette}
                  onPick={(w) => void addNicheWidget(w)}
                />
              )}
            </div>
          ),
        },
        {
          id: "properties",
          label: "Properties",
          content: (
            <div data-testid="designer-props-rail">
              {fieldInspector}
            </div>
          ),
        },
        {
          id: "structure",
          label: "Structure",
          content: (
            <div className="space-y-3 text-sm">
              <p className="text-xs text-muted">
                Add groups and pages here. Drag fields onto the layout canvas — not gray
                boxes. Power layout controls stay in Advanced.
              </p>
              {viewType === "form" ? (
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={addGroup}
                    className="rounded-md border border-border-subtle px-3 py-1.5 text-xs text-ink"
                  >
                    + Group
                  </button>
                  <button
                    type="button"
                    onClick={addNotebook}
                    className="rounded-md border border-border-subtle px-3 py-1.5 text-xs text-ink"
                  >
                    + Notebook
                  </button>
                </div>
              ) : null}
              <ul className="space-y-1 text-xs text-muted">
                {formChildren.map((child) => (
                  <li key={child.id} className="rounded border border-border-subtle px-2 py-1">
                    {child.kind === "group"
                      ? `Group · ${child.string || "untitled"}`
                      : `Notebook · ${child.pages.length} pages`}
                  </li>
                ))}
                {formChildren.length === 0 ? (
                  <li>No groups yet. Add a group, then drop fields on the canvas.</li>
                ) : null}
              </ul>
            </div>
          ),
        },
        {
          id: "overlay",
          label: "Overlay",
          content: proxyPreviewUrl ? (
            <OverlayEditor
              iframeRef={previewIframeRef}
              connectionId={connectionId}
              model={model}
              viewType={viewType}
              fields={fields}
              embedded
              onSaved={({ snapshotId, viewId }) => {
                if (snapshotId) setLastSnapshotId(snapshotId);
                setPreviewKey((k) => k + 1);
                setNotice(
                  viewId
                    ? `Overlay saved inherit view #${viewId}. Preview reloaded.`
                    : "Overlay saved — preview reloaded.",
                );
                void refreshSnapshots();
              }}
            />
          ) : (
            <p className="text-xs text-muted">
              Load a model to edit the live preview with overlay operations.
            </p>
          ),
        },
        {
          id: "advanced",
          label: "Advanced",
          content: (
            <div className="space-y-3" data-testid="designer-advanced-rail">
              <p className="text-xs text-muted">
                XPath inherit and arch override. Default Save is inherit. Completeness ≠ Cert ≠
                Autopilot.
              </p>
              <XPathInheritPanel
                expr={xpathExpr}
                position={xpathPosition}
                bodyXml={xpathBody}
                previewArch={xpathArchPreview}
                issues={xpathIssues}
                suggestedExpr={xpathSuggested}
                defaultInjectExpr={xpathDefaultInject}
                matchCount={xpathMatchCount}
                blocking={xpathBlocking}
                busy={busy}
                model={model}
                hasOverride={Boolean(archOverride)}
                onExprChange={(value) => {
                  setXpathExpr(value);
                  setXpathBlocking(false);
                }}
                onPositionChange={setXpathPosition}
                onBodyChange={setXpathBody}
                onPreview={() => void runXpathPreview()}
                onUseNamedLocator={(value) => {
                  setXpathExpr(value);
                  setXpathBlocking(false);
                  setNotice("Switched to a named locator. Preview again before save.");
                }}
                onUseAsOverride={() => {
                  setArch(xpathArchPreview);
                  setArchOverride(xpathArchPreview);
                  setNotice("Arch override set from XPath preview. Save will use inherit arch.");
                }}
                onSave={() => void onSaveXpathInherit()}
                onClearOverride={() => {
                  setArchOverride(null);
                  setNotice("Cleared arch override — Save uses canvas spec again.");
                }}
              />
            </div>
          ),
        },
      ]}
    />
  );
}
