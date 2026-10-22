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
            <div>
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
            <div className="designer-drawer-in" data-testid="designer-props-rail">
              {fieldInspector}
            </div>
          ),
        },
        {
          id: "structure",
          label: "Structure",
          content: (
            <div className="space-y-4 text-sm">
              <p className="text-xs leading-relaxed text-muted">
                Add groups and pages here, then drag fields onto the layout canvas. Power
                layout controls live in Advanced.
              </p>
              {viewType === "form" ? (
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={addGroup}
                    className="h-8 rounded-md border border-border-strong px-3 text-xs font-medium text-ink hover:bg-surface-overlay active:scale-[0.97]"
                  >
                    Add group
                  </button>
                  <button
                    type="button"
                    onClick={addNotebook}
                    className="h-8 rounded-md border border-border-strong px-3 text-xs font-medium text-ink hover:bg-surface-overlay active:scale-[0.97]"
                  >
                    Add notebook
                  </button>
                </div>
              ) : null}
              <ul className="space-y-px text-xs">
                {formChildren.map((child) => (
                  <li
                    key={child.id}
                    className="flex min-h-8 items-center justify-between gap-3 rounded-md px-2 hover:bg-surface-raised"
                  >
                    <span className="truncate text-ink">
                      {child.kind === "group"
                        ? child.string || "Untitled group"
                        : "Notebook"}
                    </span>
                    <span className="shrink-0 text-subtle">
                      {child.kind === "group"
                        ? "Group"
                        : `${child.pages.length} ${child.pages.length === 1 ? "page" : "pages"}`}
                    </span>
                  </li>
                ))}
                {formChildren.length === 0 ? (
                  <li className="text-muted">No groups yet. Add a group, then drop fields on the canvas.</li>
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
                    : "Overlay saved. Preview reloaded.",
                );
                void refreshSnapshots();
              }}
            />
          ) : (
            <p className="text-xs leading-relaxed text-muted">
              Load a model to edit the live preview with overlay operations.
            </p>
          ),
        },
        {
          id: "advanced",
          label: "Advanced",
          content: (
            <div className="space-y-3" data-testid="designer-advanced-rail">
              <p className="text-xs leading-relaxed text-muted">
                XPath inherit and arch override. Save writes an inherit view unless you set an
                override here. A complete draft is not the same as certified, and neither means Autopilot-ready.
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
                  setNotice("Cleared the arch override. Save uses the canvas spec again.");
                }}
              />
            </div>
          ),
        },
      ]}
    />
  );
}
