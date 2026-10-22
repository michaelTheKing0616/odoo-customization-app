"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  Connection,
  FieldRow,
  ModelRow,
  ModuleRow,
  PromotedModuleRow,
  ViewRow,
  DeploymentPanel,
} from "@/lib/api";

export type OverviewBrowserTab = "modules" | "models" | "fields" | "views";
export type OverviewSection = "home" | "models" | "develop";

export type OverviewLibraryStats = {
  available: boolean;
  books: number | null;
  loans: number | null;
  active_loans: number | null;
  overdue_loans: number | null;
};

export function useOverviewPageState(connectionId: string) {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [tab, setTab] = useState<OverviewBrowserTab>("models");
  const [section, setSection] = useState<OverviewSection>("home");
  const [modules, setModules] = useState<ModuleRow[]>([]);
  const [models, setModels] = useState<ModelRow[]>([]);
  const [selectedModel, setSelectedModel] = useState("res.partner");
  const [fields, setFields] = useState<FieldRow[]>([]);
  const [views, setViews] = useState<ViewRow[]>([]);
  const [modelQuery, setModelQuery] = useState("");
  const [modelPickerQuery, setModelPickerQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [exportBusy, setExportBusy] = useState(false);
  const [exportNotice, setExportNotice] = useState<string | null>(null);
  const [techName, setTechName] = useState("custom_export");
  const [displayName, setDisplayName] = useState("Custom Export");
  const [installMode, setInstallMode] = useState<"python" | "data">("python");
  const [includeExtensions, setIncludeExtensions] = useState(true);
  const [extendModels, setExtendModels] = useState("res.partner");
  const [extraDepends, setExtraDepends] = useState("");
  const [selectedDepends, setSelectedDepends] = useState<string[]>([]);
  const [installedModules, setInstalledModules] = useState<ModuleRow[]>([]);
  const [dependsQuery, setDependsQuery] = useState("");
  const [validationId, setValidationId] = useState<string | null>(null);
  const [validatedZip, setValidatedZip] = useState<string | null>(null);
  const [showPromoteConfirm, setShowPromoteConfirm] = useState(false);
  const [confirmPhrase, setConfirmPhrase] = useState("");
  const [promoted, setPromoted] = useState<PromotedModuleRow[]>([]);
  const [uninstallTarget, setUninstallTarget] = useState<string | null>(null);
  const [uninstallPhrase, setUninstallPhrase] = useState("");
  const [jobBanner, setJobBanner] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [sandboxLogTail, setSandboxLogTail] = useState<string | null>(null);
  const [suggestNotice, setSuggestNotice] = useState<string | null>(null);
  const [deploymentPanel, setDeploymentPanel] = useState<DeploymentPanel | null>(null);
  const [storeReadiness, setStoreReadiness] = useState<
    import("@/lib/api").StoreReadinessReport | null
  >(null);
  const [storeReadyExport, setStoreReadyExport] = useState(false);
  const [migrationAssist, setMigrationAssist] = useState<
    import("@/lib/api").MigrationAssist | null
  >(null);
  const [sandboxApproximation, setSandboxApproximation] = useState<string | null>(null);
  const [shStagingSuggestion, setShStagingSuggestion] = useState<string | null>(null);
  const [libraryStats, setLibraryStats] = useState<OverviewLibraryStats | null>(null);
  const [probing, setProbing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        // Models/apps counts now come from the live snapshot (LiveDatabaseSection); no listModels/listModules(apps) here.
        const [conn, promo, installed] = await Promise.all([
          api.getConnection(connectionId),
          api.listPromotedModules(connectionId),
          api.listModules(connectionId, {
            applicationsOnly: false,
            installedOnly: true,
          }),
        ]);
        if (cancelled) return;
        setConnection(conn);
        if (conn) {
          api.getMigrationAssist(connectionId).then(setMigrationAssist).catch(() => null);
        }
        setPromoted(promo);
        setInstalledModules(installed);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load");
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

  /** Library playbook stats, loaded only when the live snapshot shows the x_lib_book model. */
  const loadLibraryStats = useCallback(async () => {
    try {
      const stats = await api.libraryStats(connectionId);
      setLibraryStats(stats.available ? {
        available: true,
        books: stats.books,
        loans: stats.loans,
        active_loans: stats.active_loans,
        overdue_loans: stats.overdue_loans,
      } : null);
    } catch {
      // Stats are optional; ignore if RPC fails
    }
  }, [connectionId]);

  const filteredModels = useMemo(() => {
    const q = modelQuery.trim().toLowerCase();
    if (!q) return models.slice(0, 200);
    return models.filter(
      (m) =>
        m.model.toLowerCase().includes(q) || m.name.toLowerCase().includes(q),
    );
  }, [models, modelQuery]);

  const filteredInstalledModules = useMemo(() => {
    const q = dependsQuery.trim().toLowerCase();
    const rows = installedModules.filter((m) => m.name !== "base");
    if (!q) return rows.slice(0, 80);
    return rows
      .filter(
        (m) =>
          m.name.toLowerCase().includes(q) ||
          (m.shortdesc || "").toLowerCase().includes(q),
      )
      .slice(0, 80);
  }, [installedModules, dependsQuery]);

  return {
    connection,
    setConnection,
    tab,
    setTab,
    section,
    setSection,
    modules,
    models,
    selectedModel,
    setSelectedModel,
    fields,
    views,
    modelQuery,
    setModelQuery,
    modelPickerQuery,
    setModelPickerQuery,
    error,
    setError,
    loading,
    exportBusy,
    setExportBusy,
    exportNotice,
    setExportNotice,
    techName,
    setTechName,
    displayName,
    setDisplayName,
    installMode,
    setInstallMode,
    includeExtensions,
    setIncludeExtensions,
    extendModels,
    setExtendModels,
    extraDepends,
    setExtraDepends,
    selectedDepends,
    setSelectedDepends,
    dependsQuery,
    setDependsQuery,
    validationId,
    setValidationId,
    validatedZip,
    setValidatedZip,
    showPromoteConfirm,
    setShowPromoteConfirm,
    confirmPhrase,
    setConfirmPhrase,
    promoted,
    setPromoted,
    uninstallTarget,
    setUninstallTarget,
    uninstallPhrase,
    setUninstallPhrase,
    jobBanner,
    setJobBanner,
    activeJobId,
    setActiveJobId,
    jobStatus,
    setJobStatus,
    sandboxLogTail,
    setSandboxLogTail,
    suggestNotice,
    setSuggestNotice,
    deploymentPanel,
    setDeploymentPanel,
    storeReadiness,
    setStoreReadiness,
    storeReadyExport,
    setStoreReadyExport,
    migrationAssist,
    sandboxApproximation,
    setSandboxApproximation,
    shStagingSuggestion,
    setShStagingSuggestion,
    libraryStats,
    loadLibraryStats,
    probing,
    setProbing,
    filteredModels,
    filteredInstalledModules,
  };
}

export type OverviewPageState = ReturnType<typeof useOverviewPageState>;
