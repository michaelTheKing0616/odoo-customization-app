"use client";

import { useEffect } from "react";
import { api, type FieldRow } from "@/lib/api";
import { useSyncShellContext } from "@/lib/use-sync-shell-context";
import { useDesignerCanvasSnapshot } from "@/components/designer/useDesignerCanvasSnapshot";
import { useDesignerPageBootstrap } from "@/components/designer/useDesignerPageBootstrap";
import { useDesignerModelLoad } from "@/components/designer/useDesignerModelLoad";
import { useDesignerFieldOps } from "@/components/designer/useDesignerFieldOps";
import {
  applyFieldNamesToCanvas as runApplyFieldNamesToCanvas,
  loadExistingView as runLoadExistingView,
} from "@/components/designer/loadExistingView";
import {
  applyFieldNamesDeps,
  bootstrapDeps,
  canvasSnapshotParts,
  canvasSnapshotSetters,
  fieldOpsDeps,
  loadExistingViewDeps,
  modelLoadDeps,
} from "@/components/designer/designerPageDeps";
import {
  inspectorInput,
  mutationsInput,
  persistInput,
  viewSpecsInput,
} from "@/components/designer/designerPageHookInputs";
import { useDesignerPageState } from "@/components/designer/useDesignerPageState";

export function useDesignerPageModel(connectionId: string) {
  const s = useDesignerPageState();
  useSyncShellContext({ model: s.model, viewType: s.viewType });

  const { canvasSnapshot, applyCanvasSnapshot } = useDesignerCanvasSnapshot(
    canvasSnapshotParts(s),
    canvasSnapshotSetters(s),
  );

  useEffect(() => {
    const skip = s.historySkipRef.current;
    if (skip === "reset") {
      s.history.reset(canvasSnapshot);
      s.historySkipRef.current = null;
      return;
    }
    if (skip === "apply") {
      s.historySkipRef.current = null;
      return;
    }
    s.history.record(canvasSnapshot, {
      label: s.pendingHistoryLabelRef.current,
      coalesceKey: s.pendingCoalesceRef.current,
    });
    s.pendingHistoryLabelRef.current = undefined;
    s.pendingCoalesceRef.current = undefined;
  }, [canvasSnapshot, s.history.record, s.history.reset]);

  const {
    refreshSnapshots,
    announceAction,
    liveOdooUrl,
    proxyPreviewUrl,
  } = useDesignerPageBootstrap(bootstrapDeps(s, connectionId));

  function applyFieldNamesToCanvas(names: string[], rows: FieldRow[]) {
    runApplyFieldNamesToCanvas(applyFieldNamesDeps(s), names, rows);
  }

  const {
    loadModelFields,
    refreshModelFieldsOnly,
    appendFieldToCurrentLayout,
    ensureFieldsForModel,
  } = useDesignerModelLoad(modelLoadDeps(s, connectionId, applyFieldNamesToCanvas));

  async function loadExistingView() {
    await runLoadExistingView(loadExistingViewDeps(s, connectionId));
  }

  const { addNicheWidget, removeFormField, createNewFieldWithInject } =
    useDesignerFieldOps(
      fieldOpsDeps(
        s,
        connectionId,
        announceAction,
        appendFieldToCurrentLayout,
        refreshModelFieldsOnly,
      ),
    );

  return {
    ...s,
    api,
    connectionId,
    canvasSnapshot,
    applyCanvasSnapshot,
    refreshSnapshots,
    announceAction,
    liveOdooUrl,
    proxyPreviewUrl,
    loadModelFields,
    refreshModelFieldsOnly,
    appendFieldToCurrentLayout,
    ensureFieldsForModel,
    loadExistingView,
    addNicheWidget,
    removeFormField,
    createNewFieldWithInject,
    viewSpecsInput: viewSpecsInput(s),
    mutationsInput: mutationsInput(s, connectionId, announceAction),
    persistInput: persistInput(s, connectionId, {
      canvasSnapshot,
      applyCanvasSnapshot,
      refreshSnapshots,
      loadExistingView,
      announceAction,
    }),
    inspectorInput: inspectorInput(s, connectionId, appendFieldToCurrentLayout),
  };
}

export type DesignerPageModel = ReturnType<typeof useDesignerPageModel>;
