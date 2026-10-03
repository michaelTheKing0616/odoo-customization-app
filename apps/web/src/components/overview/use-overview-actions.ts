"use client";

import { api } from "@/lib/api";
import { JobPollError, pollJob } from "@/lib/jobs";
import { buildExportOptions, downloadBase64Zip } from "./overview-helpers";
import type { OverviewPageState } from "./use-overview-page-state";

export function useOverviewActions(connectionId: string, s: OverviewPageState) {
  async function refreshPromoted() {
    const rows = await api.listPromotedModules(connectionId);
    s.setPromoted(rows);
  }

  function toggleDepend(name: string) {
    s.setSelectedDepends((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name],
    );
  }

  async function onSuggestDepends() {
    s.setSuggestNotice(null);
    s.setError(null);
    try {
      const res = await api.suggestDepends(connectionId);
      const merged = Array.from(
        new Set([...s.selectedDepends, ...res.suggested.filter((n) => n !== "base")]),
      );
      s.setSelectedDepends(merged);
      s.setSuggestNotice(
        res.message ||
          `Suggested ${res.suggested.length} depend(s)` +
            (res.from_relations.length
              ? ` from ${res.from_relations.length} relation(s)`
              : ""),
      );
    } catch (err) {
      s.setError(err instanceof Error ? err.message : "Suggest depends failed");
    }
  }

  async function onCancelJob() {
    if (!s.activeJobId) return;
    try {
      const job = await api.cancelJob(s.activeJobId);
      s.setJobStatus(job.status);
      s.setJobBanner(`Sandbox job ${job.id.slice(0, 8)}… ${job.status}`);
    } catch (err) {
      s.setError(err instanceof Error ? err.message : "Cancel failed");
    }
  }

  function exportOptions() {
    return buildExportOptions({
      techName: s.techName,
      displayName: s.displayName,
      installMode: s.installMode,
      includeExtensions: s.includeExtensions,
      extendModels: s.extendModels,
      extraDepends: s.extraDepends,
      selectedDepends: s.selectedDepends,
    });
  }

  async function onExportModule() {
    s.setExportBusy(true);
    s.setExportNotice(null);
    s.setError(null);
    try {
      const res = await api.exportModule(connectionId, exportOptions(), {
        store_ready: s.storeReadyExport,
      });
      downloadBase64Zip(res.filename, res.content_base64);
      s.setDeploymentPanel(res.deployment_panel ?? null);
      s.setStoreReadiness(res.store_readiness ?? null);
      const warn =
        res.warnings && res.warnings.length
          ? ` Warnings: ${res.warnings.slice(0, 2).join(" · ")}`
          : "";
      s.setExportNotice(
        `Downloaded ${res.filename} (Odoo ${res.target_major ?? "?"} · ${res.manifest_version ?? "?"} · ${res.model_count} models, ${res.view_count} views, ${res.report_count ?? 0} reports).${warn}`,
      );
    } catch (err) {
      s.setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      s.setExportBusy(false);
    }
  }

  async function onSandboxRun() {
    s.setExportBusy(true);
    s.setExportNotice(null);
    s.setError(null);
    s.setJobBanner(null);
    s.setActiveJobId(null);
    s.setJobStatus(null);
    s.setSandboxLogTail(null);
    s.setValidationId(null);
    s.setValidatedZip(null);
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
      s.setSandboxApproximation(
        res.approximation ? res.approximation_label ?? "Approximate validation" : null,
      );
      s.setShStagingSuggestion(res.sh_staging_suggestion ?? null);
      s.setSandboxApproximation(
        res.approximation ? res.approximation_label ?? "Approximate validation" : null,
      );
      s.setShStagingSuggestion(res.sh_staging_suggestion ?? null);

      if (res.job_id) {
        s.setActiveJobId(res.job_id);
        s.setJobStatus("queued");
        s.setJobBanner(`Sandbox job ${res.job_id.slice(0, 8)}… queued`);
        const job = await pollJob(res.job_id, {
          fetchJob: (id) => api.getJob(id),
          onUpdate: (j) => {
            s.setJobStatus(j.status);
            s.setJobBanner(`Sandbox job ${j.id.slice(0, 8)}… ${j.status}`);
          },
        });
        const result = (job.result ?? {}) as {
          ok?: boolean;
          message?: string;
          log_tail?: string;
          validation_id?: string | null;
          zip_base64?: string | null;
        };
        s.setActiveJobId(null);
        s.setJobStatus(job.status);
        if (result.ok && result.validation_id && result.zip_base64) {
          s.setValidationId(result.validation_id);
          s.setValidatedZip(result.zip_base64);
          s.setJobBanner(`Sandbox job succeeded`);
          s.setSandboxLogTail(null);
          s.setExportNotice(
            `Sandbox OK: ${result.message ?? "validated"}. Validation ${result.validation_id.slice(0, 8)}… ready to promote (2h).`,
          );
        } else {
          s.setJobBanner(`Sandbox job finished without validation`);
          s.setExportNotice(`Sandbox failed: ${result.message ?? "unknown"}`);
          s.setSandboxLogTail(result.log_tail || null);
          s.setError(result.message || "Sandbox failed");
        }
        return;
      }

      if (res.ok && res.validation_id && res.zip_base64) {
        s.setValidationId(res.validation_id);
        s.setValidatedZip(res.zip_base64);
        s.setExportNotice(
          `Sandbox OK: ${res.message}. Validation ${res.validation_id.slice(0, 8)}… ready to promote (2h).`,
        );
      } else {
        s.setExportNotice(`Sandbox failed: ${res.message}`);
        s.setSandboxLogTail(res.log_tail || null);
        s.setError(res.message || "Sandbox failed");
      }
    } catch (err) {
      if (err instanceof JobPollError) {
        s.setJobBanner(
          err.job?.status === "cancelled"
            ? `Sandbox job cancelled`
            : `Sandbox job failed`,
        );
        s.setJobStatus(err.job?.status ?? "failed");
        s.setActiveJobId(null);
        const result = (err.job?.result ?? {}) as { log_tail?: string };
        s.setSandboxLogTail(result.log_tail || null);
        s.setError(err.message);
      } else {
        s.setError(err instanceof Error ? err.message : "Sandbox failed");
      }
    } finally {
      s.setExportBusy(false);
    }
  }

  async function onPromote() {
    if (!s.validationId || !s.validatedZip) {
      s.setError("Run sandbox successfully before promote");
      return;
    }
    if (s.confirmPhrase.trim() !== "I understand the risks") {
      s.setError("Type exactly: I understand the risks");
      return;
    }
    s.setExportBusy(true);
    s.setExportNotice(null);
    s.setError(null);
    try {
      const res = await api.promoteModule(connectionId, {
        zip_base64: s.validatedZip,
        validation_id: s.validationId,
        confirm_advanced: true,
        confirm_phrase: s.confirmPhrase.trim(),
      });
      s.setExportNotice(
        `Promoted ${res.module} via ${res.method} (state=${res.module_state ?? "n/a"}).`,
      );
      s.setShowPromoteConfirm(false);
      s.setValidationId(null);
      s.setValidatedZip(null);
      s.setConfirmPhrase("");
      await refreshPromoted();
    } catch (err) {
      s.setError(err instanceof Error ? err.message : "Promote failed");
    } finally {
      s.setExportBusy(false);
    }
  }

  async function onUninstall() {
    if (!s.uninstallTarget) return;
    if (s.uninstallPhrase.trim() !== "I understand the risks") {
      s.setError("Type exactly: I understand the risks");
      return;
    }
    s.setExportBusy(true);
    s.setError(null);
    s.setExportNotice(null);
    try {
      const res = await api.uninstallModule(connectionId, {
        module_name: s.uninstallTarget,
        confirm_advanced: true,
        confirm_phrase: s.uninstallPhrase.trim(),
      });
      s.setExportNotice(
        res.residual_models?.length
          ? `${res.message}. Residuals: ${res.residual_models.join(", ")}`
          : res.message,
      );
      s.setUninstallTarget(null);
      s.setUninstallPhrase("");
      await refreshPromoted();
    } catch (err) {
      s.setError(err instanceof Error ? err.message : "Uninstall failed");
    } finally {
      s.setExportBusy(false);
    }
  }

  function onReprobe() {
    void (async () => {
      s.setProbing(true);
      s.setError(null);
      try {
        await api.probeConnection(connectionId);
        const refreshed = await api.getConnection(connectionId);
        s.setConnection(refreshed);
      } catch (err) {
        s.setError(err instanceof Error ? err.message : "Probe failed");
      } finally {
        s.setProbing(false);
      }
    })();
  }

  async function onRefreshReadiness() {
    await api.probeConnection(connectionId);
    const refreshed = await api.getConnection(connectionId);
    s.setConnection(refreshed);
  }

  async function onRefreshHealth() {
    const refreshed = await api.getConnection(connectionId);
    s.setConnection(refreshed);
  }

  return {
    toggleDepend,
    onSuggestDepends,
    onCancelJob,
    onExportModule,
    onSandboxRun,
    onPromote,
    onUninstall,
    onReprobe,
    onRefreshReadiness,
    onRefreshHealth,
  };
}

export type OverviewPageActions = ReturnType<typeof useOverviewActions>;
