"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { ModuleSpecEditor, type ModuleSpecDoc } from "@/components/ModuleSpecEditor";
import { ModuleSpecApplyBar } from "@/components/modulespec/ModuleSpecApplyBar";
import { ModuleSpecHandoffBar } from "@/components/modulespec/ModuleSpecHandoffBar";
import { ModuleSpecHonestyBanners } from "@/components/modulespec/ModuleSpecHonestyBanners";
import { ModuleSpecIdentityCard } from "@/components/modulespec/ModuleSpecIdentityCard";
import { ModuleSpecReadiness } from "@/components/modulespec/ModuleSpecReadiness";
import { ModuleSpecSessionBar } from "@/components/modulespec/ModuleSpecSessionBar";
import { ModuleSpecShell } from "@/components/modulespec/ModuleSpecShell";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import {
  api,
  ConfirmationRequiredError,
  Connection,
  type ValidateLiveResult,
} from "@/lib/api";
import { pollJob } from "@/lib/jobs";
import {
  mutationAllowed,
  mutationBlockedReason,
  scaffoldApplyAllowed,
  scaffoldApplyBlockedReason,
  scaffoldOptsFromSpec,
  connectionSupports,
} from "@/lib/capabilities";
import { isStockReuseDraft } from "@/lib/draft-form-preview";
import { viewDesignerHref } from "@/lib/builderForm";
import {
  cloneModuleSpec,
  emptyModuleSpec,
} from "@/lib/modulespec-types";
import {
  completenessNote,
  downloadZipBase64,
  hasModuleSpecContent,
  isSpecDirty,
  localReadiness,
  moduleSpecErrorTitle,
  moduleSpecJourneyFromState,
  moduleSpecSessionState,
  moduleSpecSummary,
  primaryDesignerModel,
  sessionSubmitHint,
  type ModuleSpecBusy,
} from "@/lib/modulespec-journey";
import { odooMenuUrl, odooViewUrl } from "@/lib/odoo-urls";

const CONFIRM_PHRASE = "I understand the risks";
const DRAFT_KEY = (cid: string) => `modulespec-draft:${cid}`;

export default function ModuleSpecPageInner() {
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const connectionId = params.id;
  const projectId = search.get("project");

  const [connection, setConnection] = useState<Connection | null>(null);
  const [spec, setSpec] = useState<ModuleSpecDoc>(emptyModuleSpec());
  const [baseline, setBaseline] = useState<ModuleSpecDoc>(emptyModuleSpec());
  const [hydrated, setHydrated] = useState(false);
  const sessionHydratedRef = useRef(false);
  const [projectName, setProjectName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<ModuleSpecBusy>(null);
  const [importWarnings, setImportWarnings] = useState<string[]>([]);
  const [genConfirmOpen, setGenConfirmOpen] = useState(false);
  const [canDevCode, setCanDevCode] = useState(false);
  const [odooAppUrl, setOdooAppUrl] = useState<string | null>(null);
  const [walkthroughConfirmOpen, setWalkthroughConfirmOpen] = useState(false);
  const [savedOnce, setSavedOnce] = useState(Boolean(projectId));
  const [applied, setApplied] = useState(false);
  const [liveResult, setLiveResult] = useState<ValidateLiveResult | null>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const conn = await api.getConnection(connectionId);
      setConnection(conn);
      if (projectId) {
        const project = await api.getProject(connectionId, projectId);
        setProjectName(project.name);
        const next = (project.spec_json || emptyModuleSpec()) as ModuleSpecDoc;
        setSpec(next);
        setBaseline(cloneModuleSpec(next));
        setSavedOnce(true);
        return;
      }
      if (!sessionHydratedRef.current) {
        sessionHydratedRef.current = true;
        try {
          const raw = sessionStorage.getItem(DRAFT_KEY(connectionId));
          if (raw) {
            const parsed = JSON.parse(raw) as ModuleSpecDoc;
            setSpec(parsed);
            setBaseline(cloneModuleSpec(parsed));
            const modelCount = Array.isArray(parsed.models) ? parsed.models.length : 0;
            setNotice(
              modelCount > 0
                ? `Restored ModuleSpec from this browser session (${modelCount} model(s)).`
                : "Restored session draft — but it has 0 models. Go back to Draft Studio, re-draft, then Open ModuleSpec again.",
            );
          }
        } catch {
          /* ignore corrupt session JSON */
        }
      }
    } finally {
      setHydrated(true);
    }
  }, [connectionId, projectId]);

  useEffect(() => {
    sessionHydratedRef.current = false;
    setHydrated(false);
  }, [connectionId, projectId]);

  useEffect(() => {
    load().catch((err: Error) => {
      setError(err.message);
      setHydrated(true);
      setFailed(true);
    });
  }, [load]);

  useEffect(() => {
    if (!hydrated || projectId) return;
    try {
      sessionStorage.setItem(DRAFT_KEY(connectionId), JSON.stringify(spec));
    } catch {
      /* ignore */
    }
  }, [spec, connectionId, projectId, hydrated]);

  useEffect(() => {
    setLiveResult(null);
  }, [spec]);

  async function onSaveProject() {
    setBusy("save");
    setError(null);
    setNotice(null);
    try {
      if (projectId) {
        await api.updateProject(connectionId, projectId, {
          spec_json: spec as Record<string, unknown>,
        });
        setNotice("Project ModuleSpec saved.");
        setBaseline(cloneModuleSpec(spec));
        setSavedOnce(true);
      } else {
        const created = await api.createProject(connectionId, {
          name: String(spec.display_name || "ModuleSpec draft"),
          template_id: null,
          spec_json: spec as Record<string, unknown>,
        });
        setNotice(`Saved as project ${created.name}`);
        window.location.href = `/connections/${connectionId}/modulespec?project=${created.id}`;
      }
    } catch (err) {
      setFailed(true);
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(null);
    }
  }

  async function onImportFile(file: File) {
    setBusy("import");
    setError(null);
    setNotice(null);
    try {
      const res = await api.importModuleSpec(file);
      const next = res.spec as ModuleSpecDoc;
      setSpec(next);
      setImportWarnings(res.warnings || []);
      setNotice(`Imported (${res.source}): review models and unmapped blocks, then validate.`);
      setFailed(false);
    } catch (err) {
      setFailed(true);
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBusy(null);
    }
  }

  async function onGenerateUi(phrase: string) {
    setBusy("apply");
    setError(null);
    try {
      const res = await api.applyModuleSpec(connectionId, {
        spec: spec as Record<string, unknown>,
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setGenConfirmOpen(false);
      setNotice(res.message);
      setApplied(true);
      setFailed(false);
      setBaseline(cloneModuleSpec(spec));
      const menuId = res.root_menu_id;
      const appUrl =
        menuId && connection?.url
          ? odooMenuUrl(connection.url, menuId, res.open_action_id)
          : connection?.url
            ? `${connection.url.replace(/\/$/, "")}/web`
            : null;
      setOdooAppUrl(appUrl);
      if (res.warnings?.length) setImportWarnings(res.warnings);
    } catch (err) {
      setFailed(true);
      if (err instanceof ConfirmationRequiredError) {
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Generate UI failed");
      }
    } finally {
      setBusy(null);
    }
  }

  async function onSeedWalkthrough(phrase: string) {
    setBusy("walkthrough");
    setError(null);
    try {
      const res = await api.seedModuleSpecWalkthrough(connectionId, {
        spec: spec as Record<string, unknown>,
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setWalkthroughConfirmOpen(false);
      setNotice(res.message);
      setFailed(false);
      if (res.warnings?.length) setImportWarnings(res.warnings);
      if (res.open_model && res.open_record_id && connection?.url) {
        setOdooAppUrl(
          odooViewUrl(connection.url, res.open_model, "form", null, res.open_record_id),
        );
      }
    } catch (err) {
      setFailed(true);
      if (err instanceof ConfirmationRequiredError) {
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Walkthrough seed failed");
      }
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    api
      .accountMe()
      .then((me) => {
        const role = me.workspace?.role ?? "";
        setCanDevCode(
          me.user.is_superadmin || role === "developer" || role === "admin" || role === "owner",
        );
      })
      .catch(() => setCanDevCode(false));
  }, []);

  async function onLintBlocks() {
    setBusy("lint");
    setError(null);
    try {
      const res = await api.lintModuleSpecBlocks(connectionId, spec as Record<string, unknown>);
      if (res.ok) {
        setNotice("Lint passed for all custom code blocks.");
        setFailed(false);
      } else {
        setImportWarnings(
          (res.blocks || []).flatMap((block: { issues?: { message: string }[]; source_file?: string }) =>
            (block.issues || []).map((issue) => `${block.source_file}: ${issue.message}`),
          ),
        );
        setFailed(true);
        setError("Lint found issues in custom code blocks.");
      }
    } catch (err) {
      setFailed(true);
      setError(err instanceof Error ? err.message : "Lint failed");
    } finally {
      setBusy(null);
    }
  }

  async function onValidateLive() {
    setBusy("validate");
    setError(null);
    try {
      const res = await api.validateModuleSpecLive(connectionId, {
        spec: spec as Record<string, unknown>,
      });
      setLiveResult(res);
      setFailed(!res.ok);
      setNotice(res.message || (res.ok ? "Live validate passed." : "Live validate found issues."));
    } catch (err) {
      setFailed(true);
      setError(err instanceof Error ? err.message : "Validation failed");
    } finally {
      setBusy(null);
    }
  }

  async function onExportSandbox() {
    setBusy("sandbox");
    setError(null);
    setNotice(null);
    try {
      const queued = await api.exportModuleSpecSandbox(connectionId, {
        spec: spec as Record<string, unknown>,
        async_job: true,
      });
      if (queued.job_id) {
        const job = await pollJob(queued.job_id, { fetchJob: api.getJob });
        const result = job.result as Record<string, unknown> | undefined;
        if (result?.ok) {
          setNotice(`Sandbox passed — validation ${String(result.validation_id ?? "recorded")}`);
          setFailed(false);
        } else {
          setFailed(true);
          setError(String((result?.sandbox as { message?: string })?.message ?? "Sandbox failed"));
        }
      }
    } catch (err) {
      setFailed(true);
      setError(err instanceof Error ? err.message : "Export/sandbox failed");
    } finally {
      setBusy(null);
    }
  }

  async function onDownloadZip() {
    setBusy("zip");
    setError(null);
    try {
      const res = await api.exportModuleSpecZip(connectionId, {
        spec: spec as Record<string, unknown>,
      });
      if (!res.zip_base64) {
        setFailed(true);
        setError("Zip export returned no file.");
        return;
      }
      downloadZipBase64(String(spec.technical_name || res.module || "custom_module"), res.zip_base64);
      setNotice("Module zip downloaded. Sandbox-prove before promote — promote stays human.");
      setFailed(false);
    } catch (err) {
      setFailed(true);
      setError(err instanceof Error ? err.message : "Zip export failed");
    } finally {
      setBusy(null);
    }
  }

  const canSave = mutationAllowed(connection);
  const saveBlocked = mutationBlockedReason(connection);
  const applyOpts = scaffoldOptsFromSpec(spec as Record<string, unknown>);
  const canApply = scaffoldApplyAllowed(connection, applyOpts);
  const applyBlocked = scaffoldApplyBlockedReason(connection, applyOpts);
  const barcodeModuleAllowed = connectionSupports(connection, "barcode_scan_module");
  const stockReuse = isStockReuseDraft(spec as Record<string, unknown>);
  const summary = moduleSpecSummary(spec);
  const hasContent = hasModuleSpecContent(spec);
  const dirty = isSpecDirty(spec, baseline);
  const sessionState = moduleSpecSessionState({ dirty, savedOnce, applied });
  const readiness = useMemo(() => localReadiness(spec), [spec]);
  const journey = moduleSpecJourneyFromState({
    hydrated,
    hasContent,
    busy,
    hasLiveValidation: Boolean(liveResult),
    applied,
    failed,
  });
  const designerModel = primaryDesignerModel(spec);
  const designerHref = viewDesignerHref(connectionId, designerModel || "");

  return (
    <ModuleSpecShell
      connectionId={connectionId}
      connectionName={connection?.name}
      projectName={projectName}
      projectId={projectId}
      journey={journey}
    >
      <VersionAwarenessBanner capabilities={connection?.capabilities} />
      <ModuleSpecHonestyBanners
        applyBlocked={applyBlocked}
        saveBlocked={saveBlocked}
        stockReuse={stockReuse}
        completenessNote={completenessNote(spec)}
      />
      {error ? (
        <ErrorNotice message={error} title={moduleSpecErrorTitle(error)} className="mt-0" />
      ) : null}
      {notice ? (
        <Callout variant="info" title="Notice">
          <p>{notice}</p>
        </Callout>
      ) : null}
      {importWarnings.length > 0 ? (
        <ul className="list-disc space-y-1 pl-5 text-xs text-warning">
          {importWarnings.slice(0, 10).map((warning, index) => (
            <li key={`${index}-${warning}`}>{warning}</li>
          ))}
        </ul>
      ) : null}

      <ModuleSpecSessionBar
        sessionState={sessionState}
        busy={busy !== null}
        canDiscard={dirty}
        submitLabel={sessionSubmitHint({ sessionState, projectId, applied })}
        onDiscard={() => {
          setSpec(cloneModuleSpec(baseline));
          setFailed(false);
          setNotice("Discarded unsaved edits.");
        }}
      />

      <ModuleSpecApplyBar
        busy={busy}
        canSave={canSave}
        canApply={canApply && !readiness.applyBlocked}
        canValidate={hasContent && !stockReuse}
        hasModels={summary.models > 0}
        hasContent={hasContent}
        stockReuse={stockReuse}
        projectId={projectId}
        saveBlocked={saveBlocked}
        applyBlocked={applyBlocked ?? (readiness.applyBlocked ? readiness.headline : null)}
        odooAppUrl={odooAppUrl}
        canDevCode={canDevCode}
        onImportFile={onImportFile}
        onSaveProject={() => void onSaveProject()}
        onGenerateUi={() => setGenConfirmOpen(true)}
        onDownloadZip={() => void onDownloadZip()}
        onExportSandbox={canDevCode ? () => void onExportSandbox() : undefined}
        onWalkthrough={odooAppUrl ? () => setWalkthroughConfirmOpen(true) : undefined}
      />

      <ModuleSpecIdentityCard
        value={spec}
        barcodeModuleAllowed={barcodeModuleAllowed}
        onChange={setSpec}
      />

      <ModuleSpecReadiness
        report={readiness}
        live={liveResult}
        validating={busy === "validate"}
        canValidate={hasContent && !stockReuse && busy === null}
        validateBlocked={stockReuse ? "Stock reuse has nothing to validate on this IR" : null}
        onValidate={() => void onValidateLive()}
      />

      <ModuleSpecEditor
        value={spec}
        onChange={setSpec}
        canEditCustomCode={canDevCode}
        onLintBlocks={canDevCode ? () => void onLintBlocks() : undefined}
        onExportSandbox={canDevCode ? () => void onExportSandbox() : undefined}
        lintBusy={busy === "lint"}
        sandboxBusy={busy === "sandbox"}
        designerHref={designerHref}
      />

      <ModuleSpecHandoffBar
        connectionId={connectionId}
        designerHref={designerHref}
        designerModel={designerModel}
        projectId={projectId}
        stockReuse={stockReuse}
        applied={applied}
        odooAppUrl={odooAppUrl}
      />

      <ConfirmDialogV2
        open={genConfirmOpen}
        riskLevel="danger"
        title="Generate UI from ModuleSpec"
        warning="Creates models, fields, views, menus, and smart buttons on this live Odoo connection."
        risks={[
          "Live metadata writes on custom x_* models",
          "Smart buttons use inherit views (stock forms like Contacts stay intact)",
          "Prefer sandbox first",
          "Automations remain review-only",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy === "apply"}
        onCancel={() => setGenConfirmOpen(false)}
        onConfirm={onGenerateUi}
      />
      <ConfirmDialogV2
        open={walkthroughConfirmOpen}
        riskLevel="standard"
        title="Load demo walkthrough"
        warning="Creates sample records on this live Odoo so Operations / smart buttons are not empty."
        risks={[
          "Writes data rows on custom x_* models (named Walkthrough …)",
          "Prefer sandbox first",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy === "walkthrough"}
        onCancel={() => setWalkthroughConfirmOpen(false)}
        onConfirm={onSeedWalkthrough}
      />
    </ModuleSpecShell>
  );
}
