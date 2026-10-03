"use client";

import {
  api,
  ConfirmationRequiredError,
  type Connection,
  type ValidateLiveResult,
} from "@/lib/api";
import { reportApiError } from "@/lib/api-error";
import { odooMenuUrl, odooViewUrl } from "@/lib/odoo-urls";
import { CONFIRM_PHRASE, downloadEliteZipBase64 } from "./wizard-helpers";

type UseWizardApplyArgs = {
  connectionId: string;
  connection: Connection | null;
  multiCompany: boolean;
  aiDraft: Record<string, unknown> | null;
  skipValidateLive: boolean;
  eliteValidationId: string | null;
  eliteZipBase64: string | null;
  setBusy: (value: boolean) => void;
  setError: (value: string | null) => void;
  setZipBusy: (value: boolean) => void;
  setAiNote: (value: string | null) => void;
  setEliteLintNote: (value: string | null) => void;
  setEliteLintOk: (value: boolean | null) => void;
  setEliteBusy: (value: boolean) => void;
  setEliteNote: (
    value: string | null | ((prev: string | null) => string | null),
  ) => void;
  setEliteValidationId: (value: string | null) => void;
  setEliteZipBase64: (value: string | null) => void;
  setElitePromoteConfirmOpen: (value: boolean) => void;
  setGenUiConfirmOpen: (value: boolean) => void;
  setGenUiResult: (value: string | null) => void;
  setOdooAppUrl: (value: string | null) => void;
  setAiWarnings: (value: string[]) => void;
  setWalkthroughConfirmOpen: (value: boolean) => void;
  setValidateLiveResult: (value: ValidateLiveResult | null) => void;
  setSkipValidateLive: (value: boolean) => void;
};

export function useWizardApply({
  connectionId,
  connection,
  multiCompany,
  aiDraft,
  skipValidateLive,
  eliteValidationId,
  eliteZipBase64,
  setBusy,
  setError,
  setZipBusy,
  setAiNote,
  setEliteLintNote,
  setEliteLintOk,
  setEliteBusy,
  setEliteNote,
  setEliteValidationId,
  setEliteZipBase64,
  setElitePromoteConfirmOpen,
  setGenUiConfirmOpen,
  setGenUiResult,
  setOdooAppUrl,
  setAiWarnings,
  setWalkthroughConfirmOpen,
  setValidateLiveResult,
  setSkipValidateLive,
}: UseWizardApplyArgs) {
  function draftWithMultiCompany() {
    if (!aiDraft) return null;
    return multiCompany ? { ...aiDraft, multi_company: true } : aiDraft;
  }

  async function onDownloadModuleZip() {
    const spec = draftWithMultiCompany();
    if (!spec) return;
    setZipBusy(true);
    setError(null);
    try {
      const res = await api.exportModuleSpecZip(connectionId, { spec });
      if (!res.zip_base64) {
        setError("Zip export returned no file.");
        return;
      }
      downloadEliteZipBase64(
        String(spec.technical_name || res.module || "custom_module"),
        res.zip_base64,
      );
      setAiNote(
        "Module zip downloaded. Sandbox-prove before promote — promote stays human.",
      );
    } catch (err) {
      reportApiError(err, setError, { fallback: "Zip export failed", toast: true });
    } finally {
      setZipBusy(false);
    }
  }

  async function refreshEliteLint() {
    const spec = draftWithMultiCompany();
    if (!spec) return;
    setEliteLintNote(null);
    try {
      const lint = await api.lintModuleSpecBlocks(connectionId, spec);
      const failing = (lint.blocks ?? []).filter((b) => (b.issues?.length ?? 0) > 0);
      setEliteLintOk(lint.ok && failing.length === 0);
      setEliteLintNote(
        failing.length
          ? `${failing.length} Python block(s) need fixes before promote.`
          : "Custom Python blocks lint clean.",
      );
    } catch (err) {
      setEliteLintOk(null);
      setEliteLintNote(err instanceof Error ? err.message : "Lint check failed");
    }
  }

  async function onEliteValidateModule() {
    const spec = draftWithMultiCompany();
    if (!spec) return;
    setEliteBusy(true);
    setEliteNote(null);
    setError(null);
    setEliteValidationId(null);
    setEliteZipBase64(null);
    setEliteLintOk(null);
    setEliteLintNote(null);
    try {
      const lint = await api.lintModuleSpecBlocks(connectionId, spec);
      const failing = (lint.blocks ?? []).filter((b) => (b.issues?.length ?? 0) > 0);
      setEliteLintOk(lint.ok && failing.length === 0);
      if (failing.length) {
        setEliteLintNote(
          `Lint: ${failing.length} block(s) with issues — fix or regenerate before sandbox.`,
        );
      }
      const gate = await api.eliteModuleGate(connectionId, spec);
      if (!gate.gate_passed) {
        setEliteNote(
          `Elite gate: ${(gate.gate_reasons || []).join("; ") || "scorecard below 9.0"}`,
        );
        if (gate.dimensions) {
          const dimLine = Object.entries(gate.dimensions)
            .map(([k, v]) => `${k} ${Number(v).toFixed(1)}`)
            .join(" · ");
          setEliteNote((prev) => `${prev ?? ""}${dimLine ? ` (${dimLine})` : ""}`);
        }
        return;
      }
      const res = await api.eliteModuleAutopilot(connectionId, { spec });
      if (!res.ok) {
        setEliteNote(res.message || "Sandbox validation failed.");
        return;
      }
      setEliteValidationId(res.validation_id ?? null);
      setEliteZipBase64(res.zip_base64 ?? null);
      setEliteNote(
        `Module validated in sandbox (score ${typeof res.score_0_10 === "number" ? res.score_0_10.toFixed(1) : "—"}/10). Ready to promote.`,
      );
    } catch (err) {
      reportApiError(err, setError, { fallback: "Elite validate failed", toast: true });
    } finally {
      setEliteBusy(false);
    }
  }

  async function onElitePromoteModule(phrase: string) {
    const spec = draftWithMultiCompany();
    if (!spec || !eliteValidationId || !eliteZipBase64) return;
    setEliteBusy(true);
    setError(null);
    try {
      const tech = String(spec.technical_name || "custom_module");
      const res = await api.promoteModule(connectionId, {
        technical_name: tech,
        display_name: String(spec.display_name || tech),
        zip_base64: eliteZipBase64,
        validation_id: eliteValidationId,
        install_mode: "python",
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setElitePromoteConfirmOpen(false);
      setEliteNote(res.message || `Promoted ${tech} to this connection.`);
    } catch (err) {
      reportApiError(err, setError, { fallback: "Promote failed", toast: true });
    } finally {
      setEliteBusy(false);
    }
  }

  async function onGenerateUiFromDraft(phrase: string, forceSkipValidate = false) {
    const spec = draftWithMultiCompany();
    if (!spec) return;
    setBusy(true);
    setError(null);
    setGenUiResult(null);
    setOdooAppUrl(null);
    try {
      const res = await api.applyModuleSpec(connectionId, {
        spec,
        confirm_advanced: true,
        confirm_phrase: phrase,
        skip_validate_live: forceSkipValidate || skipValidateLive,
      });
      setGenUiConfirmOpen(false);
      setGenUiResult(res.message);
      const menuId = res.root_menu_id;
      const appUrl =
        menuId && connection?.url
          ? odooMenuUrl(connection.url, menuId, res.open_action_id)
          : connection?.url
            ? `${connection.url.replace(/\/$/, "")}/web`
            : null;
      setOdooAppUrl(appUrl);
      const sb = Number(res.smart_buttons || 0);
      const hostHint =
        sb > 0
          ? " Check linked apps’ smart-button row (e.g. Contacts) — see «Where this app shows up»."
          : "";
      setAiNote(
        appUrl
          ? `${res.message} · ${sb} smart button(s). Open the app in Odoo to walk Operations → Inventory → People — you do not pick models one by one.${hostHint}`
          : `${res.message} · ${sb} smart button(s). Open Odoo’s app switcher and click this app.${hostHint}`,
      );
      if (res.warnings?.length) setAiWarnings(res.warnings);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setError(err.warning);
      } else {
        reportApiError(err, setError, { fallback: "Generate UI failed", toast: true });
      }
    } finally {
      setBusy(false);
    }
  }

  async function onSeedWalkthrough(phrase: string) {
    const spec = draftWithMultiCompany();
    if (!spec) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.seedModuleSpecWalkthrough(connectionId, {
        spec,
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setWalkthroughConfirmOpen(false);
      setAiNote(res.message);
      if (res.warnings?.length) setAiWarnings(res.warnings);
      if (res.open_model && res.open_record_id && connection?.url) {
        setOdooAppUrl(
          odooViewUrl(connection.url, res.open_model, "form", null, res.open_record_id),
        );
      }
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setError(err.warning);
      } else {
        reportApiError(err, setError, { fallback: "Walkthrough seed failed", toast: true });
      }
    } finally {
      setBusy(false);
    }
  }

  function openModuleSpecEditor() {
    if (!aiDraft) return;
    const modelCount = Array.isArray(aiDraft.models) ? aiDraft.models.length : 0;
    if (modelCount === 0) {
      setError("Draft has 0 models — create the draft again before opening ModuleSpec.");
      return;
    }
    try {
      sessionStorage.setItem(`modulespec-draft:${connectionId}`, JSON.stringify(aiDraft));
    } catch {
      setError("Could not store draft in this browser session.");
      return;
    }
    window.location.href = `/connections/${connectionId}/modulespec`;
  }

  async function onPrepareGenerateUi() {
    const spec = draftWithMultiCompany();
    if (!spec) return;
    setBusy(true);
    setError(null);
    setValidateLiveResult(null);
    setSkipValidateLive(false);
    try {
      const validation = await api.validateModuleSpecLive(connectionId, { spec });
      setValidateLiveResult(validation);
      if (validation.ok) {
        setGenUiConfirmOpen(true);
      } else {
        setError(
          `${validation.message} — fix the draft or confirm override in the dialog.`,
        );
        setGenUiConfirmOpen(true);
        setSkipValidateLive(false);
      }
    } catch (err) {
      reportApiError(err, setError, { fallback: "Validate-live failed", toast: true });
    } finally {
      setBusy(false);
    }
  }

  return {
    draftWithMultiCompany,
    onDownloadModuleZip,
    refreshEliteLint,
    onEliteValidateModule,
    onElitePromoteModule,
    onGenerateUiFromDraft,
    onSeedWalkthrough,
    openModuleSpecEditor,
    onPrepareGenerateUi,
    confirmPhrase: CONFIRM_PHRASE,
  };
}
