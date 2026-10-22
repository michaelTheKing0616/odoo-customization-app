"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type {
  EngineCompileOut,
  EngineLoadOut,
  EngineOp,
  EnginePublishOut,
  EngineRecordsOut,
  EngineViewType,
} from "@/lib/api/view-engine";
import { describeOp, indexTree } from "@/lib/viewEngineOps";
import { isPublishConflict } from "@/lib/viewDesigner2b";
import { noteWriteRefusal } from "./writeModeSignal";

export type Device = "desktop" | "tablet" | "phone";

/** A request that never reached the server (no network), as opposed to a refusal from it. */
export function isNetworkError(err: unknown): boolean {
  if (typeof navigator !== "undefined" && navigator.onLine === false) return true;
  return err instanceof TypeError && /fetch|network|load failed/i.test(err.message);
}

export function messageOf(err: unknown): string {
  noteWriteRefusal(err);
  if (err && typeof err === "object" && "message" in err) {
    const m = (err as { message?: unknown }).message;
    if (typeof m === "string" && m) return m;
  }
  if (err && typeof err === "object" && "detail" in err) {
    const d = (err as { detail?: unknown }).detail;
    if (typeof d === "string") return d;
    if (d && typeof d === "object" && "message" in d) return String((d as { message: unknown }).message);
  }
  return "Something went wrong. Try again.";
}

const VIEW_TYPES: EngineViewType[] = ["form", "list", "kanban", "search", "calendar"];

function readUrl(): { model: string; type: EngineViewType; node: string | null; record: number | null; view: number | null } {
  if (typeof window === "undefined") return { model: "res.partner", type: "form", node: null, record: null, view: null };
  const p = new URLSearchParams(window.location.search);
  const t = p.get("type");
  return {
    model: p.get("model") || "res.partner",
    type: VIEW_TYPES.includes(t as EngineViewType) ? (t as EngineViewType) : "form",
    node: p.get("node"),
    record: p.get("record") ? Number(p.get("record")) : null,
    view: p.get("view") ? Number(p.get("view")) : null,
  };
}

/** View Designer state. The server validates and compiles every change. */
export function useViewDesigner(connectionId: string) {
  const initial = useRef(readUrl());
  const [model, setModel] = useState(initial.current.model);
  const [viewType, setViewType] = useState<EngineViewType>(initial.current.type);
  /** A specific screen (e.g. one made in Ingenium); null means Odoo's default screen. */
  const [viewId, setViewId] = useState<number | null>(initial.current.view);
  const [base, setBase] = useState<EngineLoadOut | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [ops, setOps] = useState<EngineOp[]>([]);
  const [redo, setRedo] = useState<EngineOp[][]>([]);
  const [compiled, setCompiled] = useState<EngineCompileOut | null>(null);
  const [compiling, setCompiling] = useState(false);
  const [records, setRecords] = useState<EngineRecordsOut | null>(null);
  const [recordId, setRecordId] = useState<number | null>(initial.current.record);
  const [selectedIds, setSelectedIds] = useState<string[]>(initial.current.node ? [initial.current.node] : []);
  const selectedId = selectedIds.length ? selectedIds[selectedIds.length - 1] : null;
  const setSelectedId = useCallback((id: string | null) => setSelectedIds(id ? [id] : []), []);
  const [publishCount, setPublishCount] = useState(0);
  const [device, setDevice] = useState<Device>("desktop");
  const [publishing, setPublishing] = useState(false);
  const [lastPublish, setLastPublish] = useState<EnginePublishOut | null>(null);
  const [showCode, setShowCode] = useState(false);
  // Offline (SPEC): keep the last screen on view, read-only, with Retry. Nothing is edited or published blind.
  const [offline, setOffline] = useState(false);
  useEffect(() => {
    const sync = () => setOffline(!navigator.onLine);
    sync();
    window.addEventListener("online", sync);
    window.addEventListener("offline", sync);
    return () => {
      window.removeEventListener("online", sync);
      window.removeEventListener("offline", sync);
    };
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const out = await api.engineLoad(connectionId, model, viewType, viewId);
      setBase(out);
      setOffline(false);
      setOps([]);
      setRedo([]);
      setCompiled(null);
      try {
        const recs = await api.engineRecords(connectionId, model, viewType, viewId);
        setRecords(recs);
        setRecordId((cur) => (cur && recs.records.some((r) => r.id === cur) ? cur : recs.records[0]?.id ?? null));
      } catch {
        setRecords({ records: [], total: 0, fields: [], picks: { longest: null, emptiest: null } });
      }
    } catch (err) {
      if (isNetworkError(err)) {
        setOffline(true); // keep whatever screen was already loaded
      } else {
        setBase(null);
        setLoadError(messageOf(err));
      }
    } finally {
      setLoading(false);
    }
  }, [connectionId, model, viewType, viewId]);

  useEffect(() => {
    void load();
  }, [load]);

  // URL holds the view state so it can be shared and survives a refresh.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const p = new URLSearchParams(window.location.search);
    p.set("model", model);
    p.set("type", viewType);
    if (selectedId) p.set("node", selectedId);
    else p.delete("node");
    if (recordId) p.set("record", String(recordId));
    else p.delete("record");
    if (viewId) p.set("view", String(viewId));
    else p.delete("view");
    window.history.replaceState(null, "", `${window.location.pathname}?${p.toString()}`);
  }, [model, viewType, selectedId, recordId, viewId]);

  // Compile pending changes on the server; the canvas shows the server's result.
  useEffect(() => {
    if (!base || ops.length === 0) {
      setCompiled(null);
      return;
    }
    let cancelled = false;
    setCompiling(true);
    const t = window.setTimeout(async () => {
      try {
        const out = await api.engineCompile(connectionId, model, viewType, ops, viewId);
        if (!cancelled) setCompiled(out);
      } catch (err) {
        if (cancelled) return;
        toast.error(messageOf(err));
        setOps((cur) => cur.slice(0, -1));
      } finally {
        if (!cancelled) setCompiling(false);
      }
    }, 200);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, [base, ops, connectionId, model, viewType, viewId]);

  const tree = compiled?.expected_tree ?? base?.tree ?? null;
  const index = useMemo(() => (tree ? indexTree(tree) : null), [tree]);

  const fieldLabel = useCallback((name: string) => base?.fields[name]?.string || name, [base]);

  const addOp = useCallback(
    (op: EngineOp) => {
      if (offline) {
        toast.error("You're offline. Reconnect, then Retry to edit again.");
        return;
      }
      setOps((cur) => [...cur, op]);
      setRedo([]);
      if (index) {
        toast(describeOp(op, index, fieldLabel), {
          action: { label: "Undo", onClick: () => setOps((cur) => cur.slice(0, -1)) },
        });
      }
    },
    [index, fieldLabel, offline],
  );

  /** Several ops from one action (multi-select, copy rules, command bar): one toast, one undo. */
  const addOps = useCallback((next: EngineOp[], summary: string) => {
    if (!next.length || offline) return;
    setOps((cur) => [...cur, ...next]);
    setRedo([]);
    toast(summary, {
      action: { label: "Undo", onClick: () => setOps((cur) => cur.slice(0, Math.max(0, cur.length - next.length))) },
    });
  }, [offline]);

  /** Drop the draft (after it was sent for approval, scheduled or started as a layout test). */
  const clearOps = useCallback(() => {
    setOps([]);
    setRedo([]);
  }, []);

  const undo = useCallback(() => {
    setOps((cur) => {
      if (!cur.length) return cur;
      setRedo((r) => [...r, cur]);
      return cur.slice(0, -1);
    });
  }, []);

  const redoLast = useCallback(() => {
    setRedo((r) => {
      if (!r.length) return r;
      const next = r[r.length - 1];
      setOps(next);
      return r.slice(0, -1);
    });
  }, []);

  const publish = useCallback(async () => {
    if (!base || !ops.length || offline) return;
    setPublishing(true);
    try {
      const summary = index ? ops.map((o) => describeOp(o, index, fieldLabel)) : undefined;
      const out = await api.enginePublish(connectionId, model, viewType, ops, summary, {
        view_id: viewId,
        base_layer_hash: base.layer_hash ?? null,
      });
      setLastPublish(out);
      setPublishCount((n) => n + 1);
      toast.success("Published. You can also undo this later in History.", {
        description: out.role_layouts?.join(" ") || out.warnings[0],
        duration: 10000,
        action: { label: "Undo publish", onClick: () => void undoPublish(out) },
      });
      await load();
    } catch (err) {
      if (isPublishConflict(err)) {
        // Someone else published since this screen was opened: nothing was overwritten.
        toast.error(messageOf(err), { duration: 15000, action: { label: "Reload", onClick: () => void load() } });
      } else {
        toast.error(messageOf(err));
      }
    } finally {
      setPublishing(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [base, ops, connectionId, model, viewType, viewId, load, index, fieldLabel, offline]);

  const undoPublish = useCallback(
    async (out: EnginePublishOut) => {
      try {
        await api.engineRevert(connectionId, {
          model,
          view_type: viewType,
          layer_view_id: out.layer_view_id,
          mode: out.previous_arch ? "restore" : "deactivate",
          restore_arch: out.previous_arch,
          view_id: viewId,
        });
        setLastPublish(null);
        toast.success("Publish undone");
        await load();
      } catch (err) {
        toast.error(messageOf(err));
      }
    },
    [connectionId, model, viewType, viewId, load],
  );

  const record = useMemo(
    () => records?.records.find((r) => r.id === recordId) ?? null,
    [records, recordId],
  );

  return {
    model,
    setModel,
    viewType,
    setViewType,
    viewId,
    setViewId,
    base,
    loadError,
    loading,
    reload: load,
    tree,
    index,
    ops,
    addOp,
    addOps,
    clearOps,
    undo,
    redoLast,
    canRedo: redo.length > 0,
    compiled,
    compiling,
    records,
    record,
    recordId,
    setRecordId,
    selectedId,
    setSelectedId,
    selectedIds,
    setSelectedIds,
    publishCount,
    offline,
    bumpHistory: () => setPublishCount((n) => n + 1),
    device,
    setDevice,
    publish,
    publishing,
    lastPublish,
    undoPublish,
    showCode,
    setShowCode,
    fieldLabel,
  };
}

export type ViewDesignerState = ReturnType<typeof useViewDesigner>;
