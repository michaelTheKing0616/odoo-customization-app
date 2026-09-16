"use client";

import { useCallback, useEffect } from "react";
import type { Dispatch, SetStateAction } from "react";
import {
  getApiBase,
  type Connection,
  type PreviewTheme,
  type SnapshotRow,
} from "@/lib/api";
import type { NicheWidgetEntry } from "@/components/designer/NicheWidgetPalette";
import type { ViewType } from "@/components/designer/designer-model";
import { odooViewUrl, pickStandaloneWindowAction, sameOriginPreviewUrl } from "@/lib/odoo-urls";
export type DesignerPageBootstrapDeps = {
  connectionId: string;
  api: any;
  viewType: ViewType;
  model: string;
  setModel: (v: string) => void;
  connection: Connection | null;
  setConnection: Dispatch<SetStateAction<Connection | null>>;
  setError: (v: string | null) => void;
  setNotice: (v: string | null) => void;
  setPreviewTheme: Dispatch<SetStateAction<PreviewTheme | null>>;
  setNicheWidgets: Dispatch<SetStateAction<NicheWidgetEntry[]>>;
  setColorPalette: Dispatch<
    SetStateAction<Array<{ index: number; name: string }>>
  >;
  setSnapshots: Dispatch<SetStateAction<SnapshotRow[]>>;
  canvasFlashId: string | null;
  setCanvasFlashId: Dispatch<SetStateAction<string | null>>;
  toolbarFlash: string | null;
  setToolbarFlash: Dispatch<SetStateAction<string | null>>;
  setWindowActionId: Dispatch<SetStateAction<number | null>>;
  windowActionId: number | null;
  previewKey: number;
  setLiveFailed: Dispatch<SetStateAction<boolean>>;
};

export function useDesignerPageBootstrap(deps: DesignerPageBootstrapDeps) {
  const {
    connectionId,
    api,
    viewType,
    model,
    setModel,
    connection,
    setConnection,
    setError,
    setNotice,
    setPreviewTheme,
    setNicheWidgets,
    setColorPalette,
    setSnapshots,
    canvasFlashId,
    setCanvasFlashId,
    toolbarFlash,
    setToolbarFlash,
    setWindowActionId,
    windowActionId,
    previewKey,
    setLiveFailed,
  } = deps;

  const refreshSnapshots = useCallback(async () => {
    try {
      const snaps = await api.listSnapshots(connectionId);
      setSnapshots(snaps.filter((s: SnapshotRow) => s.resource_type === "view"));
    } catch {
      setSnapshots([]);
    }
  }, [api, connectionId, setSnapshots]);

  useEffect(() => {
    api
      .getConnection(connectionId)
      .then(setConnection)
      .catch((err: Error) => setError(err.message));
    refreshSnapshots().catch(() => undefined);
    api
      .getPreviewTheme(connectionId)
      .then(setPreviewTheme)
      .catch(() => setPreviewTheme(null));
  }, [api, connectionId, refreshSnapshots, setConnection, setError, setPreviewTheme]);

  useEffect(() => {
    if (!connectionId) return;
    api
      .listNicheWidgets(connectionId, viewType)
      .then((res: { widgets: NicheWidgetEntry[]; color_palette: Array<{ index: number; name: string }> }) => {
        setNicheWidgets(res.widgets);
        setColorPalette(res.color_palette);
      })
      .catch(() => {
        setNicheWidgets([]);
        setColorPalette([]);
      });
  }, [api, connectionId, viewType, setNicheWidgets, setColorPalette]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const fromQuery = new URLSearchParams(window.location.search).get("model");
    if (fromQuery) setModel(fromQuery);
  }, [setModel]);

  useEffect(() => {
    if (!canvasFlashId || typeof document === "undefined") return;
    // Prefer the structural editor (editable drop target), not the Odoo-style preview —
    // both used to share data-canvas-id so scrollIntoView stopped at the preview on top.
    const el =
      document.querySelector(`[data-structure-id="${canvasFlashId}"]`) ??
      document.querySelector(`[data-canvas-id="${canvasFlashId}"]`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
    const t = window.setTimeout(() => setCanvasFlashId(null), 2200);
    return () => window.clearTimeout(t);
  }, [canvasFlashId, setCanvasFlashId]);

  useEffect(() => {
    if (!toolbarFlash) return;
    const t = window.setTimeout(() => setToolbarFlash(null), 1800);
    return () => window.clearTimeout(t);
  }, [toolbarFlash, setToolbarFlash]);

  function announceAction(message: string, flashId?: string | null, toolbarKey?: string) {
    setNotice(message);
    if (flashId) setCanvasFlashId(flashId);
    if (toolbarKey) setToolbarFlash(toolbarKey);
  }

  useEffect(() => {
    if (!connectionId || !model.trim()) {
      setWindowActionId(null);
      return;
    }
    let cancelled = false;
    api
      .listWindowActions(connectionId, { model: model.trim(), standaloneOnly: true })
      .then((rows: unknown) => {
        if (cancelled) return;
        setWindowActionId(pickStandaloneWindowAction(rows as Parameters<typeof pickStandaloneWindowAction>[0], viewType));
      })
      .catch(() => {
        if (!cancelled) setWindowActionId(null);
      });
    return () => {
      cancelled = true;
    };
  }, [api, connectionId, model, viewType, setWindowActionId]);

  const liveOdooUrl =
    connection?.url && model
      ? odooViewUrl(connection.url, model, viewType, windowActionId)
      : null;
  const proxyPreviewUrl = model
    ? sameOriginPreviewUrl(connectionId, model, viewType, getApiBase())
    : null;

  useEffect(() => {
    setLiveFailed(false);
  }, [proxyPreviewUrl, previewKey, model, viewType, setLiveFailed]);

  return {
    refreshSnapshots,
    announceAction,
    liveOdooUrl,
    proxyPreviewUrl,
  };
}
