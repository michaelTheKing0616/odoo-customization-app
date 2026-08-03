"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { CapabilityProbePanel } from "@/components/CapabilityProbePanel";
import { HealthCheckBanner } from "@/components/HealthCheckBanner";
import { EePlaybooksPanel } from "@/components/EePlaybooksPanel";
import { DomainPlaybooksPanel } from "@/components/DomainPlaybooksPanel";
import { StudioFeatureRecipesPanel } from "@/components/StudioFeatureRecipesPanel";
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
import { JobPollError, pollJob } from "@/lib/jobs";

type Tab = "modules" | "models" | "fields" | "views";

function downloadBase64Zip(filename: string, contentBase64: string) {
  const bin = atob(contentBase64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const blob = new Blob([bytes], { type: "application/zip" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function BrowserPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [tab, setTab] = useState<Tab>("models");
  const [modules, setModules] = useState<ModuleRow[]>([]);
  const [models, setModels] = useState<ModelRow[]>([]);
  const [selectedModel, setSelectedModel] = useState("res.partner");
  const [fields, setFields] = useState<FieldRow[]>([]);
  const [views, setViews] = useState<ViewRow[]>([]);
  const [modelQuery, setModelQuery] = useState("");
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
  const [libraryStats, setLibraryStats] = useState<{
    available: boolean;
    books: number | null;
    loans: number | null;
    active_loans: number | null;
    overdue_loans: number | null;
  } | null>(null);
  const [probing, setProbing] = useState(false);

  async function refreshPromoted() {
    const rows = await api.listPromotedModules(connectionId);
    setPromoted(rows);
  }

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [conn, mods, modsAll, promo, installed] = await Promise.all([
          api.getConnection(connectionId),
          api.listModules(connectionId, true),
          api.listModels(connectionId),
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
        if (conn) {
          api.getMigrationAssist(connectionId).then(setMigrationAssist).catch(() => null);
        }
        setModules(mods);
        setModels(modsAll);
        setPromoted(promo);
        setInstalledModules(installed);
        if (modsAll.some((m) => m.model === "res.partner")) {
          setSelectedModel("res.partner");
        } else if (modsAll[0]) {
          setSelectedModel(modsAll[0].model);
        }
        if (modsAll.some((m) => m.model === "x_lib_book")) {
          try {
            const stats = await api.libraryStats(connectionId);
            if (!cancelled && stats.available) {
              setLibraryStats({
                available: true,
                books: stats.books,
                loans: stats.loans,
                active_loans: stats.active_loans,
                overdue_loans: stats.overdue_loans,
              });
            }
          } catch {
            // Stats are optional — ignore if RPC fails
          }
        } else if (!cancelled) {
          setLibraryStats(null);
        }
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

  useEffect(() => {
    if (tab !== "fields" && tab !== "views") return;
    let cancelled = false;
    async function loadDetail() {
      setError(null);
      try {
        if (tab === "fields") {
          const rows = await api.listFields(connectionId, selectedModel);
          if (!cancelled) setFields(rows);
        } else {
          const rows = await api.listViews(connectionId, selectedModel);
          if (!cancelled) setViews(rows);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load detail");
        }
      }
    }
    loadDetail();
    return () => {
      cancelled = true;
    };
  }, [connectionId, selectedModel, tab]);

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

  function toggleDepend(name: string) {
    setSelectedDepends((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name],
    );
  }

  async function onSuggestDepends() {
    setSuggestNotice(null);
    setError(null);
    try {
      const res = await api.suggestDepends(connectionId);
      const merged = Array.from(
        new Set([...selectedDepends, ...res.suggested.filter((n) => n !== "base")]),
      );
      setSelectedDepends(merged);
      setSuggestNotice(
        res.message ||
          `Suggested ${res.suggested.length} depend(s)` +
            (res.from_relations.length
              ? ` from ${res.from_relations.length} relation(s)`
              : ""),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Suggest depends failed");
    }
  }

  async function onCancelJob() {
    if (!activeJobId) return;
    try {
      const job = await api.cancelJob(activeJobId);
      setJobStatus(job.status);
      setJobBanner(`Sandbox job ${job.id.slice(0, 8)}… ${job.status}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cancel failed");
    }
  }

  function exportOptions() {
    const extend = extendModels
      .split(/[\s,]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    const freeForm = extraDepends
      .split(/[\s,]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    const depends = Array.from(new Set([...selectedDepends, ...freeForm]));
    return {
      technical_name: techName,
      display_name: displayName,
      install_mode: installMode,
      include_extensions: includeExtensions,
      extend_models: extend.length ? extend : null,
      depends: depends.length ? depends : null,
    };
  }

  async function onExportModule() {
    setExportBusy(true);
    setExportNotice(null);
    setError(null);
    try {
      const res = await api.exportModule(connectionId, exportOptions(), {
        store_ready: storeReadyExport,
      });
      downloadBase64Zip(res.filename, res.content_base64);
      setDeploymentPanel(res.deployment_panel ?? null);
      setStoreReadiness(res.store_readiness ?? null);
      const warn =
        res.warnings && res.warnings.length
          ? ` Warnings: ${res.warnings.slice(0, 2).join(" · ")}`
          : "";
      setExportNotice(
        `Downloaded ${res.filename} (Odoo ${res.target_major ?? "?"} · ${res.manifest_version ?? "?"} · ${res.model_count} models, ${res.view_count} views, ${res.report_count ?? 0} reports).${warn}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExportBusy(false);
    }
  }

  async function onSandboxRun() {
    setExportBusy(true);
    setExportNotice(null);
    setError(null);
    setJobBanner(null);
    setActiveJobId(null);
    setJobStatus(null);
    setSandboxLogTail(null);
    setValidationId(null);
    setValidatedZip(null);
    try {
      const opts = exportOptions();
      const res = await api.runSandbox(connectionId, {
        technical_name: opts.technical_name,
        display_name: opts.display_name,
        include_extensions: opts.include_extensions,
        extend_models: opts.extend_models,
        depends: opts.depends,
        // Preload peer/stock depends in sandbox so the candidate zip can install
        extra_modules: opts.depends,
        keep_alive: false,
        async_job: true,
      });
      setSandboxApproximation(
        res.approximation ? res.approximation_label ?? "Approximate validation" : null,
      );
      setShStagingSuggestion(res.sh_staging_suggestion ?? null);
      setSandboxApproximation(
        res.approximation ? res.approximation_label ?? "Approximate validation" : null,
      );
      setShStagingSuggestion(res.sh_staging_suggestion ?? null);

      if (res.job_id) {
        setActiveJobId(res.job_id);
        setJobStatus("queued");
        setJobBanner(`Sandbox job ${res.job_id.slice(0, 8)}… queued`);
        const job = await pollJob(res.job_id, {
          fetchJob: (id) => api.getJob(id),
          onUpdate: (j) => {
            setJobStatus(j.status);
            setJobBanner(`Sandbox job ${j.id.slice(0, 8)}… ${j.status}`);
          },
        });
        const result = (job.result ?? {}) as {
          ok?: boolean;
          message?: string;
          log_tail?: string;
          validation_id?: string | null;
          zip_base64?: string | null;
        };
        setActiveJobId(null);
        setJobStatus(job.status);
        if (result.ok && result.validation_id && result.zip_base64) {
          setValidationId(result.validation_id);
          setValidatedZip(result.zip_base64);
          setJobBanner(`Sandbox job succeeded`);
          setSandboxLogTail(null);
          setExportNotice(
            `Sandbox OK: ${result.message ?? "validated"}. Validation ${result.validation_id.slice(0, 8)}… ready to promote (2h).`,
          );
        } else {
          setJobBanner(`Sandbox job finished without validation`);
          setExportNotice(`Sandbox failed: ${result.message ?? "unknown"}`);
          setSandboxLogTail(result.log_tail || null);
          setError(result.message || "Sandbox failed");
        }
        return;
      }

      if (res.ok && res.validation_id && res.zip_base64) {
        setValidationId(res.validation_id);
        setValidatedZip(res.zip_base64);
        setExportNotice(
          `Sandbox OK: ${res.message}. Validation ${res.validation_id.slice(0, 8)}… ready to promote (2h).`,
        );
      } else {
        setExportNotice(`Sandbox failed: ${res.message}`);
        setSandboxLogTail(res.log_tail || null);
        setError(res.message || "Sandbox failed");
      }
    } catch (err) {
      if (err instanceof JobPollError) {
        setJobBanner(
          err.job?.status === "cancelled"
            ? `Sandbox job cancelled`
            : `Sandbox job failed`,
        );
        setJobStatus(err.job?.status ?? "failed");
        setActiveJobId(null);
        const result = (err.job?.result ?? {}) as { log_tail?: string };
        setSandboxLogTail(result.log_tail || null);
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Sandbox failed");
      }
    } finally {
      setExportBusy(false);
    }
  }

  async function onPromote() {
    if (!validationId || !validatedZip) {
      setError("Run sandbox successfully before promote");
      return;
    }
    if (confirmPhrase.trim() !== "I understand the risks") {
      setError('Type exactly: I understand the risks');
      return;
    }
    setExportBusy(true);
    setExportNotice(null);
    setError(null);
    try {
      const res = await api.promoteModule(connectionId, {
        zip_base64: validatedZip,
        validation_id: validationId,
        confirm_advanced: true,
        confirm_phrase: confirmPhrase.trim(),
      });
      setExportNotice(
        `Promoted ${res.module} via ${res.method} (state=${res.module_state ?? "n/a"}).`,
      );
      setShowPromoteConfirm(false);
      setValidationId(null);
      setValidatedZip(null);
      setConfirmPhrase("");
      await refreshPromoted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Promote failed");
    } finally {
      setExportBusy(false);
    }
  }

  async function onUninstall() {
    if (!uninstallTarget) return;
    if (uninstallPhrase.trim() !== "I understand the risks") {
      setError("Type exactly: I understand the risks");
      return;
    }
    setExportBusy(true);
    setError(null);
    setExportNotice(null);
    try {
      const res = await api.uninstallModule(connectionId, {
        module_name: uninstallTarget,
        confirm_advanced: true,
        confirm_phrase: uninstallPhrase.trim(),
      });
      setExportNotice(
        res.residual_models?.length
          ? `${res.message}. Residuals: ${res.residual_models.join(", ")}`
          : res.message,
      );
      setUninstallTarget(null);
      setUninstallPhrase("");
      await refreshPromoted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Uninstall failed");
    } finally {
      setExportBusy(false);
    }
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: "modules", label: "Apps" },
    { id: "models", label: "Models" },
    { id: "fields", label: "Fields" },
    { id: "views", label: "Views" },
  ];

  return (
    <main className="min-h-screen bg-[radial-gradient(ellipse_at_top,_#3d2a38_0%,_#1a1218_50%,_#0c090b_100%)] px-6 py-10 text-[#f4eef2]">
      <div className="mx-auto max-w-6xl">
        <div className="mt-4 flex flex-wrap items-center gap-4">
          <Link href="/connect" className="text-sm text-[#c9a9c0] hover:underline">
            ← Connections
          </Link>
          <Link
            href={`/connections/${connectionId}/wizard`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            Wizard
          </Link>
          <Link
            href={`/connections/${connectionId}/builder`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            Builder
          </Link>
          <Link
            href={`/connections/${connectionId}/projects`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            Drafts
          </Link>
          <Link
            href={`/connections/${connectionId}/modulespec`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            ModuleSpec
          </Link>
          <Link
            href={`/connections/${connectionId}/designer`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            View designer
          </Link>
          <Link
            href={`/connections/${connectionId}/automations`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            Automations
          </Link>
          <Link
            href={`/connections/${connectionId}/approvals`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            Approvals
          </Link>
          <Link
            href={`/connections/${connectionId}/approvals`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            Approvals
          </Link>
          <Link
            href={`/connections/${connectionId}/access`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            Access
          </Link>
          <Link
            href={`/connections/${connectionId}/reminders`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            Reminders
          </Link>
          <Link
            href={`/connections/${connectionId}/import`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            Bulk import
          </Link>
          <Link
            href={`/connections/${connectionId}/id-generator`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            ID Generator
          </Link>
          <Link
            href={`/connections/${connectionId}/id-generator`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            ID Generator
          </Link>
          <Link
            href={`/connections/${connectionId}/power-ops`}
            className="text-sm font-semibold text-[#c9a9c0] hover:underline"
          >
            Power Ops
          </Link>
          <Link
            href={`/connections/${connectionId}/bulk-suite`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            Bulk Suite
          </Link>
          <Link
            href={`/connections/${connectionId}/cron-manager`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            Cron Manager
          </Link>
          <Link
            href={`/connections/${connectionId}/housekeeping`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            Housekeeping
          </Link>
          <Link
            href={`/connections/${connectionId}/bulk-suite`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            Bulk Suite
          </Link>
          <Link
            href={`/connections/${connectionId}/cron-manager`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            Cron Manager
          </Link>
          <Link
            href={`/connections/${connectionId}/housekeeping`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            Housekeeping
          </Link>
          <Link
            href={`/connections/${connectionId}/journal`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            Change journal
          </Link>
          <Link
            href={`/connections/${connectionId}/config`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            Settings
          </Link>
          <Link
            href={`/connections/${connectionId}/menus`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            Menus
          </Link>
          <Link
            href={`/connections/${connectionId}/reports`}
            className="text-sm text-[#c9a9c0] hover:underline"
          >
            Reports
          </Link>
          <Link href="/pipelines" className="text-sm text-[#c9a9c0] hover:underline">
            Multi-env promote
          </Link>
        </div>
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl text-[#faf6f9]">
          Metadata browser
        </h1>
        <p className="mt-1 text-sm text-[#8f7a88]">
          {connection
            ? `${connection.name} · ${connection.url} · ${connection.server_version ?? ""}`
            : connectionId}
          {" · "}
          read-only
        </p>
        {connection && (
          <CapabilityProbePanel
            capabilities={connection.capabilities}
            className="mt-3"
            refreshing={probing}
            onRefresh={() => {
              void (async () => {
                setProbing(true);
                setError(null);
                try {
                  await api.probeConnection(connectionId);
                  const refreshed = await api.getConnection(connectionId);
                  setConnection(refreshed);
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Probe failed");
                } finally {
                  setProbing(false);
                }
              })();
            }}
          />
        )}
        {connection && (
          <HealthCheckBanner
            connectionId={connectionId}
            connection={connection}
            onRefreshConnection={async () => {
              const refreshed = await api.getConnection(connectionId);
              setConnection(refreshed);
            }}
          />
        )}
        <EePlaybooksPanel connectionId={connectionId} className="mt-3" />
        <DomainPlaybooksPanel connectionId={connectionId} className="mt-3" />
        <StudioFeatureRecipesPanel className="mt-3" />

        {libraryStats?.available && (
          <div className="mt-6 flex flex-wrap gap-6 border border-[#3d2a38] bg-[#0f1a16]/60 px-4 py-3 text-sm">
            <span className="text-[#a8909e]">Library</span>
            <span>
              <span className="text-[#8f7a88]">Books </span>
              <span className="font-mono text-[#c9a9c0]">{libraryStats.books ?? "—"}</span>
            </span>
            <span>
              <span className="text-[#8f7a88]">Loans </span>
              <span className="font-mono text-[#c9a9c0]">{libraryStats.loans ?? "—"}</span>
            </span>
            <span>
              <span className="text-[#8f7a88]">Active </span>
              <span className="font-mono text-[#c9a9c0]">
                {libraryStats.active_loans ?? "—"}
              </span>
            </span>
            <span>
              <span className="text-[#8f7a88]">Overdue </span>
              <span className="font-mono text-[#f0a8a0]">
                {libraryStats.overdue_loans ?? "—"}
              </span>
            </span>
          </div>
        )}

        <div className="mt-8 flex flex-wrap gap-2 border-b border-[#3d2a38] pb-3">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`px-3 py-1.5 text-sm ${
                tab === t.id
                  ? "bg-[#714B67] text-white"
                  : "border border-[#3d2a38] text-[#d4c4ce]"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {(tab === "fields" || tab === "views") && (
          <label className="mt-4 block max-w-md text-sm">
            <span className="text-[#a8909e]">Model</span>
            <input
              list="model-options"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
            />
            <datalist id="model-options">
              {models.slice(0, 500).map((m) => (
                <option key={m.id} value={m.model}>
                  {m.name}
                </option>
              ))}
            </datalist>
          </label>
        )}

        {error && <p className="mt-4 text-sm text-[#f0a8a0]">{error}</p>}
        {exportNotice && <p className="mt-4 text-sm text-[#c9a9c0]">{exportNotice}</p>}
        {suggestNotice && (
          <p className="mt-4 text-sm text-[#c9a9c0]">{suggestNotice}</p>
        )}
        {jobBanner && (
          <div
            className="mt-4 flex flex-wrap items-center gap-3 border border-[#3d2a38] bg-[#1a1218]/80 px-3 py-2 text-sm text-[#c9a9c0]"
            role="status"
          >
            <span>{jobBanner}</span>
            {activeJobId &&
              (jobStatus === "queued" || jobStatus === "running") && (
                <button
                  type="button"
                  onClick={() => onCancelJob()}
                  className="border border-[#f0a8a0] px-2 py-0.5 text-xs text-[#f0a8a0]"
                >
                  Cancel
                </button>
              )}
          </div>
        )}
        {sandboxLogTail && (
          <details className="mt-4 border border-[#3d2a38] bg-[#0c090b]/80 p-3">
            <summary className="cursor-pointer text-sm text-[#f0a8a0]">
              Sandbox log
            </summary>
            <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap text-xs text-[#d4c4ce]">
              {sandboxLogTail}
            </pre>
          </details>
        )}
        {loading && <p className="mt-4 text-sm text-[#8f7a88]">Loading…</p>}

        <section className="mt-8 border border-[#3d2a38] bg-[#0f1a16]/60 p-5">
          <h2 className="font-[family-name:var(--font-display)] text-xl text-[#faf6f9]">
            Export, sandbox &amp; promote
          </h2>
          <p className="mt-1 text-sm text-[#8f7a88]">
            Package new <code className="text-[#c9a9c0]">x_*</code> models and/or extensions to
            stock models (inherit) → sandbox → promote after validation + confirm. One zip per
            connection major (manifest{" "}
            {connection?.capabilities?.major
              ? `${connection.capabilities.major}.0.x`
              : "from probe"}
            ). Local sandbox uses matching-major Docker (odoo:16–19) on :18069.
            See <span className="text-[#c9a9c0]">skills/module-interop.md</span>.
          </p>
          {deploymentPanel ? (
            <div
              className="mt-4 rounded border border-[#3d2a38] bg-[#0c090b]/80 p-4 text-sm"
              data-testid="deployment-panel"
            >
              <p className="font-medium text-[#faf6f9]">{deploymentPanel.title}</p>
              <p className="mt-2 text-[#a8909e]">{deploymentPanel.body}</p>
              <ul className="mt-2 list-disc pl-5 text-[#8f7a88]">
                {deploymentPanel.options.map((opt) => (
                  <li key={opt}>{opt}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {sandboxApproximation ? (
            <p
              className="mt-3 rounded border border-amber-900/50 bg-amber-950/30 p-3 text-sm text-amber-100"
              data-testid="sandbox-approximation"
            >
              {sandboxApproximation}
              {shStagingSuggestion ? (
                <span className="mt-2 block text-amber-200/90">{shStagingSuggestion}</span>
              ) : null}
            </p>
          ) : null}
          {storeReadiness ? (
            <div
              className="mt-4 rounded border border-[#3d2a38] bg-[#0c090b]/80 p-4 text-sm"
              data-testid="store-readiness-report"
            >
              <p className="font-medium text-[#faf6f9]">
                Store readiness — {storeReadiness.message}
              </p>
              <p className="mt-1 text-xs text-[#8f7a88]">{storeReadiness.disclaimer}</p>
              <ul className="mt-2 space-y-1 text-[#a8909e]">
                {storeReadiness.items.map((item) => (
                  <li key={item.key}>
                    [{item.status}] {item.label}: {item.message}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {migrationAssist?.eligible ? (
            <div
              className="mt-4 rounded border border-[#3d2a38] bg-[#0c090b]/80 p-4 text-sm"
              data-testid="migration-assist-panel"
            >
              <p className="font-medium text-[#faf6f9]">{migrationAssist.title}</p>
              <p className="mt-2 text-[#a8909e]">{migrationAssist.body}</p>
              {migrationAssist.unlocks.length > 0 ? (
                <ul className="mt-3 list-disc pl-5 text-[#8f7a88]">
                  {migrationAssist.unlocks.map((u) => (
                    <li key={u.key}>
                      {u.label}: {u.online_status} → {u.sh_status} — {u.reason}
                    </li>
                  ))}
                </ul>
              ) : null}
              <p className="mt-2 text-xs text-[#8f7a88]">{migrationAssist.disclaimer}</p>
              <div className="mt-2 flex flex-wrap gap-3">
                {migrationAssist.docs_links.map((link) => (
                  <a
                    key={link.url}
                    href={link.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[#c9a9c0] hover:underline"
                  >
                    {link.label}
                  </a>
                ))}
              </div>
            </div>
          ) : null}
          {storeReadiness ? (
            <div
              className="mt-4 rounded border border-[#3d2a38] bg-[#0c090b]/80 p-4 text-sm"
              data-testid="store-readiness-report"
            >
              <p className="font-medium text-[#faf6f9]">
                Store readiness — {storeReadiness.message}
              </p>
              <p className="mt-1 text-xs text-[#8f7a88]">{storeReadiness.disclaimer}</p>
              <ul className="mt-2 space-y-1 text-[#a8909e]">
                {storeReadiness.items.map((item) => (
                  <li key={item.key}>
                    [{item.status}] {item.label}: {item.message}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {migrationAssist?.eligible ? (
            <div
              className="mt-4 rounded border border-[#3d2a38] bg-[#0c090b]/80 p-4 text-sm"
              data-testid="migration-assist-panel"
            >
              <p className="font-medium text-[#faf6f9]">{migrationAssist.title}</p>
              <p className="mt-2 text-[#a8909e]">{migrationAssist.body}</p>
              {migrationAssist.unlocks.length > 0 ? (
                <ul className="mt-3 list-disc pl-5 text-[#8f7a88]">
                  {migrationAssist.unlocks.map((u) => (
                    <li key={u.key}>
                      {u.label}: {u.online_status} → {u.sh_status} — {u.reason}
                    </li>
                  ))}
                </ul>
              ) : null}
              <p className="mt-2 text-xs text-[#8f7a88]">{migrationAssist.disclaimer}</p>
              <div className="mt-2 flex flex-wrap gap-3">
                {migrationAssist.docs_links.map((link) => (
                  <a
                    key={link.url}
                    href={link.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[#c9a9c0] hover:underline"
                  >
                    {link.label}
                  </a>
                ))}
              </div>
            </div>
          ) : null}
          <div className="mt-4 flex flex-wrap items-end gap-3">
            <label className="text-sm">
              <span className="text-[#a8909e]">Technical name</span>
              <input
                value={techName}
                onChange={(e) => setTechName(e.target.value)}
                className="mt-1 block w-48 border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
              />
            </label>
            <label className="text-sm">
              <span className="text-[#a8909e]">Display name</span>
              <input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="mt-1 block w-56 border border-[#3d2a38] bg-[#0c090b] px-3 py-2 text-sm"
              />
            </label>
            <label className="text-sm">
              <span className="text-[#a8909e]">Install mode</span>
              <select
                value={installMode}
                onChange={(e) =>
                  setInstallMode(e.target.value as "python" | "data")
                }
                className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2 text-sm"
              >
                <option value="python">python (local Docker)</option>
                <option value="data">data (remote import)</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm text-[#d4c4ce]">
              <input
                type="checkbox"
                checked={includeExtensions}
                onChange={(e) => setIncludeExtensions(e.target.checked)}
              />
              Include stock-model extensions
            </label>
            <label className="text-sm">
              <span className="text-[#a8909e]">Extend models</span>
              <input
                value={extendModels}
                onChange={(e) => setExtendModels(e.target.value)}
                placeholder="res.partner, sale.order"
                className="mt-1 block w-64 border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
              />
            </label>
            <label className="flex items-center gap-2 text-sm text-[#d4c4ce]">
              <input
                type="checkbox"
                checked={storeReadyExport}
                onChange={(e) => setStoreReadyExport(e.target.checked)}
              />
              Apps Store packaging assist (icon, listing page, readiness report)
            </label>
            <label className="flex items-center gap-2 text-sm text-[#d4c4ce]">
              <input
                type="checkbox"
                checked={storeReadyExport}
                onChange={(e) => setStoreReadyExport(e.target.checked)}
              />
              Apps Store packaging assist (icon, listing page, readiness report)
            </label>
            <button
              type="button"
              disabled={exportBusy}
              onClick={onExportModule}
              className="h-10 border border-[#c9a9c0] px-4 text-sm text-[#c9a9c0] disabled:opacity-60"
            >
              Download zip
            </button>
            <button
              type="button"
              disabled={exportBusy}
              onClick={onSandboxRun}
              className="h-10 bg-[#714B67] px-4 text-sm font-semibold text-white disabled:opacity-60"
            >
              {exportBusy ? "Running…" : "Sandbox install"}
            </button>
            <button
              type="button"
              disabled={exportBusy || !validationId}
              onClick={() => setShowPromoteConfirm(true)}
              className="h-10 border border-[#f0c090] px-4 text-sm text-[#f0c090] disabled:opacity-40"
            >
              Promote to connection
            </button>
          </div>
          <div className="mt-4 w-full max-w-2xl">
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-sm text-[#a8909e]">Extra depends (peer / stock modules)</p>
              <button
                type="button"
                disabled={exportBusy}
                onClick={() => onSuggestDepends()}
                className="border border-[#c9a9c0] px-2 py-0.5 text-xs text-[#c9a9c0] disabled:opacity-50"
              >
                Suggest depends
              </button>
            </div>
            {selectedDepends.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {selectedDepends.map((name) => (
                  <button
                    key={name}
                    type="button"
                    onClick={() => toggleDepend(name)}
                    className="border border-[#4a3a48] bg-[#1a1218] px-2 py-1 font-mono text-xs text-[#c9a9c0]"
                    title="Click to remove"
                  >
                    {name} ×
                  </button>
                ))}
              </div>
            )}
            <input
              value={dependsQuery}
              onChange={(e) => setDependsQuery(e.target.value)}
              placeholder="Search installed modules…"
              className="mt-2 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 text-sm"
            />
            <div className="mt-2 max-h-40 overflow-y-auto border border-[#1e2f29] bg-[#0c090b]/80">
              {filteredInstalledModules.map((m) => {
                const checked = selectedDepends.includes(m.name);
                return (
                  <label
                    key={m.id}
                    className="flex cursor-pointer items-start gap-2 border-b border-[#1e2f29] px-3 py-2 text-sm last:border-b-0 hover:bg-[#1a1218]/60"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleDepend(m.name)}
                      className="mt-1"
                    />
                    <span>
                      <span className="font-mono text-[#c9a9c0]">{m.name}</span>
                      {m.shortdesc ? (
                        <span className="ml-2 text-[#8f7a88]">{m.shortdesc}</span>
                      ) : null}
                    </span>
                  </label>
                );
              })}
              {filteredInstalledModules.length === 0 && (
                <p className="px-3 py-2 text-xs text-[#8f7a88]">
                  No installed modules match.
                </p>
              )}
            </div>
            <label className="mt-2 block text-sm">
              <span className="text-[#a8909e]">
                Free-form depends (not in list)
              </span>
              <input
                value={extraDepends}
                onChange={(e) => setExtraDepends(e.target.value)}
                placeholder="peer_custom_mod, another_mod"
                className="mt-1 block w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
              />
            </label>
          </div>
          {validationId && (
            <p className="mt-3 text-xs text-[#8f7a88]">
              Validated · {validationId.slice(0, 8)}… · mode={installMode} · local Docker
              uses filesystem for python; remote promote needs data mode.
            </p>
          )}
          {showPromoteConfirm && (
            <div className="mt-4 border border-[#5a3a2a] bg-[#1a100c] p-4">
              <p className="text-sm font-medium text-[#f0c090]">Promote risks</p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-[#d0b0a0]">
                <li>Live metadata changes on this Odoo connection</li>
                <li>Uninstall may not fully reverse data</li>
                <li>Only the sandbox-validated zip will be installed</li>
              </ul>
              <label className="mt-3 block text-sm">
                <span className="text-[#a8909e]">
                  Type <code className="text-[#f0c090]">I understand the risks</code>
                </span>
                <input
                  value={confirmPhrase}
                  onChange={(e) => setConfirmPhrase(e.target.value)}
                  className="mt-1 w-full max-w-md border border-[#5a3a2a] bg-[#0c090b] px-3 py-2 text-sm"
                />
              </label>
              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  disabled={exportBusy}
                  onClick={onPromote}
                  className="h-9 bg-[#f0c090] px-4 text-sm font-semibold text-[#1a100c] disabled:opacity-60"
                >
                  Proceed
                </button>
                <button
                  type="button"
                  onClick={() => setShowPromoteConfirm(false)}
                  className="h-9 border border-[#5a3a2a] px-4 text-sm text-[#d0b0a0]"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </section>

        <section className="mt-6 border border-[#3d2a38] bg-[#0f1a16]/40 p-5">
          <h2 className="font-[family-name:var(--font-display)] text-xl text-[#faf6f9]">
            Promoted modules
          </h2>
          <p className="mt-1 text-sm text-[#8f7a88]">
            History of modules installed via promote. Uninstall requires confirmation.
          </p>
          <ul className="mt-4 space-y-2 text-sm">
            {promoted.map((p) => (
              <li
                key={p.id}
                className="flex flex-wrap items-center justify-between gap-2 border border-[#1e2f29] px-3 py-2"
              >
                <span>
                  <span className="font-mono text-[#c9a9c0]">{p.module_name}</span>{" "}
                  <span className="text-[#8f7a88]">
                    · {p.method} · {p.status}
                  </span>
                </span>
                {p.status === "installed" && (
                  <button
                    type="button"
                    disabled={exportBusy}
                    onClick={() => {
                      setUninstallTarget(p.module_name);
                      setUninstallPhrase("");
                    }}
                    className="border border-[#f0a8a0] px-2 py-1 text-xs text-[#f0a8a0] disabled:opacity-40"
                  >
                    Uninstall
                  </button>
                )}
              </li>
            ))}
            {promoted.length === 0 && (
              <li className="text-[#8f7a88]">No promotions recorded yet.</li>
            )}
          </ul>
          {uninstallTarget && (
            <div className="mt-4 border border-[#5a3a2a] bg-[#1a100c] p-4">
              <p className="text-sm text-[#f0c090]">
                Uninstall <code className="font-mono">{uninstallTarget}</code>?
              </p>
              <label className="mt-3 block text-sm">
                <span className="text-[#a8909e]">
                  Type <code className="text-[#f0c090]">I understand the risks</code>
                </span>
                <input
                  value={uninstallPhrase}
                  onChange={(e) => setUninstallPhrase(e.target.value)}
                  className="mt-1 w-full max-w-md border border-[#5a3a2a] bg-[#0c090b] px-3 py-2 text-sm"
                />
              </label>
              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  disabled={exportBusy}
                  onClick={onUninstall}
                  className="h-9 bg-[#f0a8a0] px-4 text-sm font-semibold text-[#1a100c] disabled:opacity-60"
                >
                  Uninstall
                </button>
                <button
                  type="button"
                  onClick={() => setUninstallTarget(null)}
                  className="h-9 border border-[#5a3a2a] px-4 text-sm text-[#d0b0a0]"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </section>

        {!loading && tab === "modules" && (
          <table className="mt-6 w-full text-left text-sm">
            <thead className="text-[#8f7a88]">
              <tr>
                <th className="py-2 pr-4">Name</th>
                <th className="py-2 pr-4">Technical</th>
                <th className="py-2">State</th>
              </tr>
            </thead>
            <tbody>
              {modules.map((m) => (
                <tr key={m.id} className="border-t border-[#1e2f29]">
                  <td className="py-2 pr-4">{m.shortdesc ?? m.name}</td>
                  <td className="py-2 pr-4 font-mono text-[#c9a9c0]">{m.name}</td>
                  <td className="py-2">{m.state}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {!loading && tab === "models" && (
          <>
            <input
              value={modelQuery}
              onChange={(e) => setModelQuery(e.target.value)}
              placeholder="Filter models…"
              className="mt-4 w-full max-w-md border border-[#3d2a38] bg-[#0c090b] px-3 py-2 text-sm"
            />
            <table className="mt-4 w-full text-left text-sm">
              <thead className="text-[#8f7a88]">
                <tr>
                  <th className="py-2 pr-4">Label</th>
                  <th className="py-2 pr-4">Model</th>
                  <th className="py-2">State</th>
                </tr>
              </thead>
              <tbody>
                {filteredModels.map((m) => (
                  <tr key={m.id} className="border-t border-[#1e2f29]">
                    <td className="py-2 pr-4">{m.name}</td>
                    <td className="py-2 pr-4 font-mono text-[#c9a9c0]">{m.model}</td>
                    <td className="py-2">{m.state}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {!loading && tab === "fields" && (
          <table className="mt-6 w-full text-left text-sm">
            <thead className="text-[#8f7a88]">
              <tr>
                <th className="py-2 pr-4">Label</th>
                <th className="py-2 pr-4">Name</th>
                <th className="py-2 pr-4">Type</th>
                <th className="py-2">Flags</th>
              </tr>
            </thead>
            <tbody>
              {fields.map((f) => (
                <tr key={f.id} className="border-t border-[#1e2f29]">
                  <td className="py-2 pr-4">{f.field_description}</td>
                  <td className="py-2 pr-4 font-mono text-[#c9a9c0]">{f.name}</td>
                  <td className="py-2 pr-4">
                    {f.ttype}
                    {f.relation ? ` → ${f.relation}` : ""}
                  </td>
                  <td className="py-2 text-[#8f7a88]">
                    {[f.required && "required", f.readonly && "readonly", f.state]
                      .filter(Boolean)
                      .join(", ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {!loading && tab === "views" && (
          <ul className="mt-6 space-y-4">
            {views.map((v) => (
              <li key={v.id} className="border border-[#3d2a38] p-4">
                <p className="font-medium">
                  {v.name}{" "}
                  <span className="text-[#8f7a88]">
                    · {v.type} · #{v.id}
                  </span>
                </p>
                <pre className="mt-3 max-h-64 overflow-auto bg-[#0c090b] p-3 text-xs text-[#d4c4ce]">
                  {v.arch ?? "(no arch)"}
                </pre>
              </li>
            ))}
            {views.length === 0 && (
              <li className="text-sm text-[#8f7a88]">No views for this model.</li>
            )}
          </ul>
        )}
      </div>
    </main>
  );
}
