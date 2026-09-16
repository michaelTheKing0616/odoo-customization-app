"use client";

import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import type { Connection, FieldRow } from "@/lib/api";
import { ConfirmationRequiredError } from "@/lib/api";
import type {
  DesignerCanvasSnapshot,
  ViewType,
} from "@/components/designer/designer-model";
import type { LocatorIssue, XPathPosition } from "@/components/designer/XPathInheritPanel";
import type { useDesignerHistory } from "@/components/designer/useDesignerHistory";

const CONFIRM_PHRASE = "I understand the risks";

type HistoryApi = ReturnType<typeof useDesignerHistory<DesignerCanvasSnapshot>>;

export type DesignerPersistDeps = {
  model: string;
  connectionId: string;
  connection: Connection | null;
  viewType: ViewType;
  title: string;
  saveStrategy: "inherit" | "overwrite";
  setSaveStrategy: (v: "inherit" | "overwrite") => void;
  archOverride: string | null;
  setArchOverride: (v: string | null) => void;
  activeViewSpec: unknown;
  canvasSnapshot: DesignerCanvasSnapshot;
  history: HistoryApi;
  historySkipRef: MutableRefObject<"reset" | "apply" | null>;
  loadedViewId: number | null;
  setLoadedViewId: (v: number | null) => void;
  lastSnapshotId: string | null;
  setLastSnapshotId: Dispatch<SetStateAction<string | null>>;
  setBusy: (v: boolean) => void;
  setError: (v: string | null) => void;
  setNotice: (v: string | null) => void;
  setConfirmOverwriteOpen: (v: boolean) => void;
  setArch: (v: string) => void;
  xpathExpr: string;
  arch: string;
  xpathPosition: XPathPosition;
  xpathBody: string;
  setXpathIssues: Dispatch<SetStateAction<LocatorIssue[]>>;
  setXpathDefaultInject: Dispatch<SetStateAction<string | null>>;
  setConfirmUnlinkInheritOpen: (v: boolean) => void;
  applyCanvasSnapshot: (snapshot: DesignerCanvasSnapshot) => void;
  setXpathArchPreview: (v: string) => void;
  setXpathSuggested: (v: string | null) => void;
  setXpathMatchCount: (v: number | null) => void;
  setXpathBlocking: (v: boolean) => void;
  setPreviewKey: Dispatch<SetStateAction<number>>;
  refreshSnapshots: () => void | Promise<void>;
  loadExistingView: () => void | Promise<void>;
  announceAction: (message: string, flashId?: string | null, toolbarKey?: string) => void;
  api: any;
};

export function useDesignerPersist(deps: DesignerPersistDeps) {
  const {
    model,
    connectionId,
    connection,
    viewType,
    title,
    saveStrategy,
    setSaveStrategy,
    archOverride,
    setArchOverride,
    activeViewSpec,
    canvasSnapshot,
    history,
    historySkipRef,
    loadedViewId,
    setLoadedViewId,
    lastSnapshotId,
    setLastSnapshotId,
    setBusy,
    setError,
    setNotice,
    setConfirmOverwriteOpen,
    setArch,
    arch,
    xpathExpr,
    xpathPosition,
    xpathBody,
    setXpathIssues,
    setXpathDefaultInject,
    setXpathArchPreview,
    setXpathSuggested,
    setXpathMatchCount,
    setXpathBlocking,
    setConfirmUnlinkInheritOpen,
    applyCanvasSnapshot,
    setPreviewKey,
    refreshSnapshots,
    loadExistingView,
    announceAction,
    api,
  } = deps;

  async function onSave(opts?: {
    arch?: string;
    strategy?: "inherit" | "overwrite";
    confirm_phrase?: string;
  }) {
    if (!model) {
      setError("Load a model first");
      return;
    }
    const strategy = opts?.strategy ?? saveStrategy;
    // Stock models default to inherit — overwrite only via confirmed Power path
    if (!model.startsWith("x_") && strategy === "overwrite" && !opts?.confirm_phrase) {
      setConfirmOverwriteOpen(true);
      return;
    }
    if (strategy === "overwrite" && !opts?.confirm_phrase && model.startsWith("x_")) {
      setConfirmOverwriteOpen(true);
      return;
    }
    const useArch = opts?.arch ?? archOverride;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const saved = await api.saveView(connectionId, {
        model,
        view_type: viewType,
        name:
          strategy === "inherit"
            ? `${model}.designer.${viewType}`
            : `${model}.${viewType}`,
        view_id: strategy === "overwrite" ? (loadedViewId ?? undefined) : undefined,
        ...(useArch ? { arch: useArch } : { spec: activeViewSpec }),
        create_if_missing: true,
        strategy,
        ...(strategy === "overwrite"
          ? {
              confirm_advanced: true,
              confirm_phrase: opts?.confirm_phrase || CONFIRM_PHRASE,
            }
          : {}),
      });
      setLoadedViewId(saved.id);
      setConfirmOverwriteOpen(false);
      if (saved.snapshot_id) {
        setLastSnapshotId(saved.snapshot_id);
        setNotice(
          `Published ${viewType} view #${saved.id}. Checkpoint ${saved.snapshot_id.slice(0, 8)}… is in published history.`,
        );
      } else {
        setNotice(`Saved new ${viewType} view #${saved.id} for ${model}`);
      }
      setArch(saved.arch ?? arch);
      setArchOverride(null);
      setPreviewKey((k) => k + 1);
      if (archOverride !== null) {
        historySkipRef.current = "apply";
      }
      history.reset({ ...canvasSnapshot, archOverride: null });
      await refreshSnapshots();
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmOverwriteOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Save failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function onRepairDuplicateChrome() {
    if (!model) {
      setError("Load a model first");
      return;
    }
    if (model.startsWith("x_") || viewType !== "form") {
      setError("Fix duplicate chrome applies to stock form views (e.g. account.move).");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const out = await api.repairDesignerInherit(connectionId, {
        model,
        view_type: "form",
      });
      if (out.snapshot_id) setLastSnapshotId(out.snapshot_id);
      setNotice(out.detail || `Repair: ${out.action}`);
      await refreshSnapshots();
      await loadExistingView();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Repair failed");
    } finally {
      setBusy(false);
    }
  }

  async function onUnlinkDesignerInherit(phrase: string) {
    if (!model) {
      setError("Load a model first");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const out = await api.unlinkDesignerInherit(connectionId, {
        model,
        view_type: viewType,
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setConfirmUnlinkInheritOpen(false);
      if (out.snapshot_id) setLastSnapshotId(out.snapshot_id);
      setNotice(out.detail || `Unlink: ${out.action}`);
      await refreshSnapshots();
      await loadExistingView();
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmUnlinkInheritOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Unlink failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function runXpathPreview() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.xpathPreview(connectionId, {
        expr: xpathExpr,
        position: xpathPosition,
        body_xml: xpathBody,
        parent_arch: arch || null,
        view_type: viewType,
      });
      setXpathArchPreview(res.arch);
      const located = res.locator_issues ?? [];
      setXpathIssues(located);
      setXpathSuggested(res.suggested_expr ?? null);
      setXpathDefaultInject(res.default_inject_expr ?? null);
      setXpathMatchCount(res.match_count ?? null);
      setXpathBlocking(Boolean(res.blocking));
      if (res.blocking) {
        setNotice("XPath preview found a blocking locator issue.");
      } else if (located.some((i: LocatorIssue) => i.severity === "warning") || (res.issues?.length ?? 0) > 0) {
        setNotice("XPath preview built with upgrade-safety warnings.");
      } else {
        setNotice("XPath preview OK — named locator matches the parent view.");
      }
      return res;
    } catch (err) {
      setError(err instanceof Error ? err.message : "XPath preview failed");
      setXpathArchPreview("");
      setXpathIssues([]);
      setXpathBlocking(false);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function onSaveXpathInherit() {
    const res = await runXpathPreview();
    if (!res || res.blocking) {
      return;
    }
    await onSave({ arch: res.arch, strategy: "inherit" });
  }

  function onSessionUndo() {
    const snapshot = history.undo();
    if (!snapshot) {
      setNotice(
        lastSnapshotId
          ? "Nothing to undo in this session. Use roll back last publish to restore a snapshot."
          : "Nothing to undo in this session. Save to Odoo first creates a published checkpoint.",
      );
      return;
    }
    historySkipRef.current = "apply";
    applyCanvasSnapshot(snapshot);
    setNotice("Reverted the last unpublished canvas edit.");
  }

  function onSessionRedo() {
    const snapshot = history.redo();
    if (!snapshot) return;
    historySkipRef.current = "apply";
    applyCanvasSnapshot(snapshot);
    setNotice("Restored the unpublished canvas edit.");
  }

  async function onRollbackLastPublish() {
    if (!lastSnapshotId) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.rollbackSnapshot(connectionId, lastSnapshotId);
      setNotice(`Rolled back to snapshot — restored view #${res.id}`);
      setLastSnapshotId(null);
      await loadExistingView();
      await refreshSnapshots();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rollback failed");
    } finally {
      setBusy(false);
    }
  }

  async function onRollback(snapshotId: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await api.rollbackSnapshot(connectionId, snapshotId);
      setNotice(`Restored ${res.restored} #${res.id}`);
      if (snapshotId === lastSnapshotId) setLastSnapshotId(null);
      await loadExistingView();
      await refreshSnapshots();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rollback failed");
    } finally {
      setBusy(false);
    }
  }

  return {
    onSave,
    onRepairDuplicateChrome,
    onUnlinkDesignerInherit,
    runXpathPreview,
    onSaveXpathInherit,
    onSessionUndo,
    onSessionRedo,
    onRollbackLastPublish,
    onRollback,
  };
}
