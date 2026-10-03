"use client";

import { api } from "@/lib/api";
import { reportApiError, isApiNotFound } from "@/lib/api-error";
import { inheritHostModelFromDraft } from "@/lib/draft-models";
import type { HostInstallOffer } from "@/lib/draft-form-preview";
import { odooViewUrl, preferHostListActionId } from "@/lib/odoo-urls";
import { CONFIRM_PHRASE } from "./studio-constants";
import { downloadZipBase64 } from "./studio-helpers";
import type { StudioState } from "./use-studio-state";
import type { StudioDerived } from "./use-studio-derived";

export function useStudioOptionA(
  connectionId: string,
  s: StudioState,
  d: Pick<
    StudioDerived,
    "authoredOptionA" | "goldOptionA" | "goldId" | "inheritHost" | "hostFormName"
  >,
) {
  const {
    session,
    connection,
    goldValidationId,
    goldZipBase64,
    goldHost,
    lastSandboxFault,
    setSession,
    setBusy,
    setError,
    setCalloutTitle,
    setApplyNote,
    setLastSandboxFault,
    setGoldValidationId,
    setGoldZipBase64,
    setGoldPromoted,
    setPromoteOpen,
    setInstallOpen,
    setGoldHost,
    setOdooAppUrl,
    beginStudioAction,
    failStudio,
  } = s;
  const { authoredOptionA, goldOptionA, goldId, inheritHost, hostFormName } = d;

  async function downloadGoldZip() {
    const spec = session?.artifact;
    if (!spec) return;
    beginStudioAction();
    setBusy("zip");
    try {
      const res = await api.exportModuleSpecZip(connectionId, { spec });
      if (!res.zip_base64) {
        failStudio("zip", "Zip export returned no file.");
        return;
      }
      downloadZipBase64(String(res.module || spec.technical_name || "currency_rate_cbn"), res.zip_base64);
      setCalloutTitle("Module zip downloaded");
      setApplyNote(
        authoredOptionA
          ? "Downloaded the Option A zip. Next: Sandbox install & smoke (proof only), then Promote. Do not click Install this app."
          : "Downloaded the Option A zip. Next: Sandbox install & smoke (proof only), then Promote onto this connection. Open Accounting Settings is this Odoo — not the ephemeral sandbox.",
      );
    } catch (err) {
      failStudio("zip", err instanceof Error ? err.message : "Zip export failed");
    } finally {
      setBusy(null);
    }
  }

  async function proveGoldSandbox() {
    const spec = session?.artifact;
    if (!spec) return;
    beginStudioAction();
    setBusy("prove");
    try {
      const res = await api.proveOptionA(connectionId, { spec });
      if (res.draft) {
        setSession((cur) => (cur ? { ...cur, artifact: res.draft as Record<string, unknown> } : cur));
      }
      if (res.ok) {
        setLastSandboxFault(null);
        if (res.validation_id && res.zip_base64) {
          setGoldValidationId(res.validation_id);
          setGoldZipBase64(res.zip_base64);
          setGoldPromoted(false);
        }
        setCalloutTitle(
          res.feedback_repair?.applied ? "Sandbox proved after AI repair" : "Sandbox proved",
        );
        setApplyNote(
          res.message ||
            (res.promote_ready
              ? "Ephemeral sandbox passed and was torn down. Promote installs the zip on THIS connection. Then open Accounting Settings (not App Studio Open in Odoo)."
              : "Sandbox install passed. Promote stays human — this connection’s Odoo is where you inspect CBN, not :18069."),
        );
      } else {
        const sandboxMsg = (res.sandbox as { message?: string } | undefined)?.message;
        const msg =
          sandboxMsg ||
          (res.smoke as { message?: string } | undefined)?.message ||
          res.message ||
          "Sandbox prove failed";
        setLastSandboxFault(sandboxMsg || msg);
        const step =
          /repair budget|sandbox repair attempts|Repair with AI/i.test(res.message || "")
            ? "repair"
            : "sandbox";
        failStudio(step, res.message || msg);
        setCalloutTitle("Applied to Odoo");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Sandbox prove failed";
      setLastSandboxFault(msg);
      failStudio("sandbox", msg);
    } finally {
      setBusy(null);
    }
  }

  async function repairGoldWithAi() {
    const spec = session?.artifact;
    if (!spec) return;
    beginStudioAction();
    setBusy("repair");
    try {
      const fault =
        lastSandboxFault ||
        String(
          ((spec as Record<string, unknown>)._option_a_smoke as { message?: string } | undefined)
            ?.message ||
            ((spec as Record<string, unknown>)._sandbox_install as { message?: string } | undefined)
              ?.message ||
            "",
        );
      const res = await api.repairOptionAFeedback(connectionId, {
        spec,
        error_text: fault,
        retry_sandbox: true,
      });
      if (res.draft) {
        setSession((cur) => (cur ? { ...cur, artifact: res.draft as Record<string, unknown> } : cur));
      }
      if (res.ok && res.validation_id && res.zip_base64) {
        setLastSandboxFault(null);
        setGoldValidationId(res.validation_id);
        setGoldZipBase64(res.zip_base64);
        setGoldPromoted(false);
        setCalloutTitle("Sandbox proved after AI repair");
        setApplyNote(
          res.message ||
            "AI repair + sandbox passed. Promote stays human. Do not click Install this app.",
        );
        return;
      }
      const sandboxMsg = (res.sandbox as { message?: string } | undefined)?.message;
      const msg =
        res.feedback_repair?.message ||
        res.message ||
        sandboxMsg ||
        "AI repair did not clear the sandbox Fault";
      if (sandboxMsg) setLastSandboxFault(sandboxMsg);
      failStudio("repair", msg);
      if (res.feedback_repair?.applied) {
        setCalloutTitle("AI patched the module");
        setApplyNote(
          "The model patched files from the sandbox Fault. Retry Sandbox install & smoke, or Repair with AI again if budget remains. Do not click Install this app.",
        );
      }
    } catch (err) {
      failStudio("repair", err instanceof Error ? err.message : "AI repair failed");
    } finally {
      setBusy(null);
    }
  }

  async function promoteGoldModule(phrase: string) {
    const spec = session?.artifact;
    if (!spec || !goldValidationId || !goldZipBase64) return;
    setError(null);
    setBusy("promote");
    try {
      const tech = String(spec.technical_name || goldId || "custom_module");
      const res = await api.promoteModule(connectionId, {
        technical_name: tech,
        display_name: String(spec.display_name || tech),
        zip_base64: goldZipBase64,
        validation_id: goldValidationId,
        install_mode: "python",
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setPromoteOpen(false);
      setGoldPromoted(true);
      setCalloutTitle("Promoted to this connection");
      const host =
        inheritHostModelFromDraft(spec) ||
        inheritHostModelFromDraft(session?.artifact ?? null) ||
        inheritHost;
      const base = connection?.url?.replace(/\/$/, "") || "";
      let openActionId: number | null = null;
      let stampMsg = "";
      if (!goldOptionA && session?.id) {
        try {
          const stamped = await api.stampOptionAPromote(session.id);
          if (stamped.id) setSession(stamped);
          else if (stamped.session) setSession(stamped.session);
          openActionId =
            typeof stamped.open_action_id === "number" ? stamped.open_action_id : null;
          const stampHost =
            (typeof stamped.host_model === "string" && stamped.host_model) || host;
          stampMsg = String(stamped.message || "");
          if (Array.isArray(stamped.host_install) && stamped.host_install.length) {
            setApplyNote(stampMsg);
          }
          if (stampHost && base) {
            setOdooAppUrl(odooViewUrl(base, stampHost, "list", openActionId));
          }
        } catch {
          /* fall through to client-side resolve */
        }
      }
      if (!goldOptionA && host && base && !openActionId) {
        try {
          const actions = await api.listWindowActions(connectionId, {
            model: host,
            standaloneOnly: true,
          });
          openActionId = preferHostListActionId(actions, host);
        } catch {
          /* action resolve is best-effort */
        }
        const href = odooViewUrl(base, host, "list", openActionId);
        setOdooAppUrl(href);
        setSession((cur) => {
          if (!cur?.artifact) return cur;
          return {
            ...cur,
            artifact: {
              ...cur.artifact,
              _studio_apply: {
                root_menu_id: null,
                open_action_id: openActionId,
                host_model: host,
                applied: true,
                via: "option_a_promote",
              },
            },
          };
        });
      }
      try {
        if (goldOptionA && goldId) {
          const row = await api.goldInspect(connectionId, goldId);
          setGoldHost(row);
        }
      } catch {
        /* inspect is best-effort after promote */
      }
      const hostLabel = hostFormName || host || "the stock form";
      if (!stampMsg || !/missing/i.test(stampMsg)) {
        setApplyNote(
          goldOptionA
            ? res.message ||
                `Promoted ${tech} onto this connection. Open Invoicing → Configuration → Settings (not Settings → Currency). Service = Central Bank of Nigeria → Update now → Currencies → USD → Rates.`
            : `${res.message || `Promoted ${tech} onto this connection.`} ${
                stampMsg ||
                `Open ${hostLabel} via Sales → Quotations (not Discuss, not a new Apps tile). Markup % is on the quotation form.`
              } Do not click Install this app.`,
        );
      }
    } catch (err) {
      reportApiError(err, setError, { fallback: "Promote failed", toast: true });
    } finally {
      setBusy(null);
    }
  }

  async function installGoldHostModule(phrase: string) {
    const moduleName = goldHost?.install_module;
    if (!moduleName || phrase !== CONFIRM_PHRASE) return;
    setError(null);
    setBusy("install-host");
    try {
      const res = await api.installCommunityModule(connectionId, moduleName);
      setInstallOpen(false);
      if (!res.ok) {
        setError(res.message || `Could not install ${moduleName}`);
        return;
      }
      const row = await api.goldInspect(connectionId, goldId);
      setGoldHost(row);
      setCalloutTitle("Invoicing installed on this connection");
      setApplyNote(
        row.host_ready
          ? "Invoicing (account) is on this connection. Promote the CBN zip next, then Open Accounting Settings."
          : row.message || res.message,
      );
    } catch (err) {
      reportApiError(err, setError, { fallback: "Could not install Invoicing on this connection", toast: true });
    } finally {
      setBusy(null);
    }
  }

  async function reverifyAuthoringGate() {
    if (!session) return;
    setError(null);
    setBusy("reverify");
    try {
      const verified = await api.reverifyOptionAAuthoring({
        connection_id: connectionId,
        session_id: session.id,
        draft: session.artifact ?? undefined,
      });
      if (verified.session) setSession(verified.session);
      setCalloutTitle(verified.ok ? "Authoring gate passed" : "Authoring gate still blocked");
      setApplyNote(
        verified.message ||
          (verified.ok
            ? "Authoring gate passed — zip and sandbox unlocked. Do not click Install this app."
            : "Authoring gate still has findings. Zip stays locked. Promote stays human."),
      );
    } catch (err) {
      reportApiError(err, setError, {
        fallback: "Could not re-check the authoring gate — restart uvicorn on :8001 without --reload",
        toast: true,
      });
    } finally {
      setBusy(null);
    }
  }

  async function installAuthoredHostModule(offer: HostInstallOffer, phrase: string) {
    if (!offer.module || phrase !== CONFIRM_PHRASE) return;
    setError(null);
    setBusy("install-host");
    let installed = false;
    try {
      const res = await api.installCommunityModule(connectionId, offer.module);
      if (!res.ok) {
        setError(res.message || `Could not install ${offer.label}`);
        return;
      }
      installed = true;
      setBusy("reverify");
      const verified = await api.reverifyOptionAAuthoring({
        connection_id: connectionId,
        session_id: session?.id,
        draft: session?.artifact ?? undefined,
      });
      if (verified.session) setSession(verified.session);
      setCalloutTitle(`${offer.label} installed on this connection`);
      setApplyNote(
        verified.ok
          ? `${offer.label} (${offer.module}) is on this connection. Authoring gate passed — zip and sandbox unlocked. Do not click Install this app. Promote stays human.`
          : verified.message ||
            `${offer.label} is installed. The authoring gate still has findings. Zip stays locked.`,
      );
    } catch (err) {
      if (installed && isApiNotFound(err)) {
        setCalloutTitle(`${offer.label} install was sent`);
        setApplyNote(
          `${offer.label} (${offer.module}) was sent to this Odoo. The authoring re-check API returned 404 — kill/restart uvicorn on :8001 without --reload, hard-refresh, then Re-check authoring gate. Do not click Install this app.`,
        );
        return;
      }
      reportApiError(err, setError, {
        fallback: `Could not install ${offer.label} on this connection`,
        toast: true,
      });
    } finally {
      setBusy(null);
    }
  }

  return {
    downloadGoldZip,
    proveGoldSandbox,
    repairGoldWithAi,
    promoteGoldModule,
    installGoldHostModule,
    reverifyAuthoringGate,
    installAuthoredHostModule,
  };
}
