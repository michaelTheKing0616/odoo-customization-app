"use client";

import { useEffect } from "react";
import { api, type Connection, type ReuseModelRow } from "@/lib/api";
import {
  FALLBACK_TEMPLATES,
  dedupeTemplates,
  mapDraftCacheEntries,
  type DraftCacheEntry,
  type GalleryItem,
} from "./wizard-helpers";

type UseWizardLoadArgs = {
  connectionId: string;
  stockReuse: boolean;
  aiDraft: Record<string, unknown> | null;
  nlPrompt: string;
  stashBriefForJobAutopilot: () => void;
  setLoading: (value: boolean) => void;
  setError: (value: string | null) => void;
  setConnection: (value: Connection | null) => void;
  setTemplates: (value: import("@/lib/api").AppTemplate[]) => void;
  setComponentGallery: (value: GalleryItem[]) => void;
  setAiEnabled: (value: boolean) => void;
  setAiProviderLabel: (value: string) => void;
  setOllamaDetail: (value: string | null) => void;
  setDraftCacheEntries: (value: DraftCacheEntry[]) => void;
  setReuseCatalog: (value: ReuseModelRow[]) => void;
  setReuseCatalogStatus: (value: "loading" | "ready" | "error") => void;
  setReuseCatalogError: (value: string | null) => void;
};

export function useWizardLoad({
  connectionId,
  stockReuse,
  aiDraft,
  nlPrompt,
  stashBriefForJobAutopilot,
  setLoading,
  setError,
  setConnection,
  setTemplates,
  setComponentGallery,
  setAiEnabled,
  setAiProviderLabel,
  setOllamaDetail,
  setDraftCacheEntries,
  setReuseCatalog,
  setReuseCatalogStatus,
  setReuseCatalogError,
}: UseWizardLoadArgs) {
  useEffect(() => {
    if (!stockReuse) return;
    stashBriefForJobAutopilot();
  }, [stockReuse, connectionId, aiDraft, nlPrompt]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);

      function withTimeout<T>(p: Promise<T>, ms: number, fallback: T): Promise<T> {
        return new Promise((resolve) => {
          const t = setTimeout(() => resolve(fallback), ms);
          p.then((v) => {
            clearTimeout(t);
            resolve(v);
          }).catch(() => {
            clearTimeout(t);
            resolve(fallback);
          });
        });
      }

      try {
        // Never block the whole wizard on slow Odoo/AI status (RAG used to
        // load MiniLM inside /ai/status and freeze "Loading templates…").
        const [conn, tpls, status, gallery] = await Promise.all([
          withTimeout(api.getConnection(connectionId), 8000, null as Connection | null),
          withTimeout(api.listAppTemplates(), 5000, FALLBACK_TEMPLATES),
          withTimeout(api.aiStatus().catch(() => null), 4000, null),
          withTimeout(api.listComponentGallery().catch(() => []), 4000, []),
        ]);
        if (cancelled) return;
        if (!conn) {
          setError("Could not load connection (timeout or API down). Templates still available.");
        } else {
          setConnection(conn);
        }
        setTemplates(dedupeTemplates(tpls.length ? tpls : FALLBACK_TEMPLATES));
        setComponentGallery(gallery || []);
        setAiEnabled(Boolean(status?.enabled));
        setAiProviderLabel(status?.provider_label || "AI");
        const reachable = status?.provider_reachable ?? status?.ollama_reachable;
        const detail = status?.provider_detail ?? status?.ollama_detail;
        if (reachable === false && detail) {
          setOllamaDetail(detail);
        } else if (reachable === true) {
          setOllamaDetail(null);
        } else if (detail) {
          setOllamaDetail(detail);
        }
        try {
          const cached = await api.listDraftCache(connectionId, 10);
          setDraftCacheEntries(mapDraftCacheEntries(cached));
        } catch {
          setDraftCacheEntries([]);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load");
          setTemplates(dedupeTemplates(FALLBACK_TEMPLATES));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [connectionId]);

  useEffect(() => {
    let cancelled = false;
    async function loadCatalog() {
      setReuseCatalogStatus("loading");
      setReuseCatalogError(null);
      try {
        const rows = await api.listReuseCatalog(connectionId);
        if (cancelled) return;
        setReuseCatalog(rows);
        setReuseCatalogStatus("ready");
        if (!rows.length) {
          setReuseCatalogError(
            "No stock models returned. Check that this connection’s Odoo is running.",
          );
        }
      } catch (err) {
        if (cancelled) return;
        setReuseCatalogStatus("error");
        setReuseCatalogError(
          err instanceof Error ? err.message : "Failed to load stock Odoo models",
        );
      }
    }
    void loadCatalog();
    return () => {
      cancelled = true;
    };
  }, [connectionId]);

  async function reloadReuseCatalog() {
    setReuseCatalogStatus("loading");
    setReuseCatalogError(null);
    try {
      const rows = await api.listReuseCatalog(connectionId);
      setReuseCatalog(rows);
      setReuseCatalogStatus("ready");
      if (!rows.length) {
        setReuseCatalogError(
          "No stock models returned. Check that this connection’s Odoo is running.",
        );
      }
    } catch (err) {
      setReuseCatalogStatus("error");
      setReuseCatalogError(
        err instanceof Error ? err.message : "Failed to load stock Odoo models",
      );
    }
  }

  async function refreshDraftCacheList() {
    const cached = await api.listDraftCache(connectionId, 10).catch(() => []);
    setDraftCacheEntries(mapDraftCacheEntries(cached));
  }

  return { reloadReuseCatalog, refreshDraftCacheList };
}
