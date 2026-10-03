"use client";

import { api, ConfirmationRequiredError } from "@/lib/api";
import { reportApiError } from "@/lib/api-error";
import { inheritHostModelFromDraft } from "@/lib/draft-models";
import { odooMenuUrl, odooViewUrl } from "@/lib/odoo-urls";
import type { StudioState } from "./use-studio-state";
import type { StudioDerived } from "./use-studio-derived";

export function useStudioReview(
  connectionId: string,
  s: StudioState,
  d: Pick<StudioDerived, "inheritHost" | "hostForOpen" | "hostFormName" | "liveAppName">,
) {
  const {
    session,
    connection,
    refineInput,
    setError,
    setLocalRefineError,
    setBusy,
    setSession,
    setRefineInput,
    setHighlightIds,
    setFlashId,
    setMobileTab,
    setApplyOpen,
    setOdooAppUrl,
    setCalloutTitle,
    setApplyNote,
  } = s;
  const { inheritHost, hostForOpen, hostFormName, liveAppName } = d;

  async function submitRefine(instruction?: string) {
    const text = (instruction ?? refineInput).trim();
    if (!session || text.length < 3) return;
    setError(null);
    setLocalRefineError(null);
    setBusy("refine");
    try {
      const out = await api.refineStudioSession(session.id, text);
      if (out.needs_clarification) {
        setSession(out.session);
        return;
      }
      setSession(out.session);
      if (!instruction) setRefineInput("");
      if (!out.ok) {
        setLocalRefineError(out.error || "Could not apply that change.");
        return;
      }
      const ids = out.highlighted_field_ids || [];
      setHighlightIds(ids);
      if (ids[0]) {
        setFlashId(ids[0]);
        window.setTimeout(() => setFlashId(null), 2400);
      }
      setMobileTab("preview");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Refinement failed";
      if (/could not (map|apply)/i.test(message)) {
        setLocalRefineError(message);
        if (!instruction) setRefineInput("");
        return;
      }
      setError(message);
    } finally {
      setBusy(null);
    }
  }

  async function onApplyToOdoo(phrase: string) {
    if (!session) return;
    setError(null);
    setBusy("apply");
    try {
      const res = await api.applyStudioSession(session.id, {
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setApplyOpen(false);
      if (res.session) setSession(res.session);
      const menuId = res.root_menu_id;
      const warnings = (res.warnings || []).filter(Boolean);
      const menuSkipped = warnings.some((w) => /menus skipped/i.test(w));
      const host =
        inheritHost ||
        hostForOpen ||
        inheritHostModelFromDraft(res.session?.artifact ?? session.artifact ?? null);
      const hostUrl =
        !menuId && connection?.url && host
          ? odooViewUrl(connection.url, host, "list", res.open_action_id)
          : null;
      setOdooAppUrl(
        menuId && connection?.url
          ? odooMenuUrl(connection.url, menuId, res.open_action_id)
          : hostUrl,
      );
      setCalloutTitle("Applied to Odoo");
      const homeHint =
        "Look on the Odoo home grid (hard-refresh) — Apps search will not list a live-metadata app.";
      if (menuId) {
        const tile = String(
          (res.session?.artifact?.display_name as string | undefined) || liveAppName,
        );
        setApplyNote(`${res.message} Open in Odoo now lands on ${tile}. ${homeHint}`);
      } else if (host) {
        setApplyNote(
          `${res.message} Open in Odoo opens ${hostFormName} (Invoicing → Bills if this was vendor bills) — not a new app tile.`,
        );
      } else {
        setApplyNote(
          menuSkipped
            ? `${res.message} Menus were not created (${warnings.join("; ")}). ${homeHint}`
            : `${res.message} No app menu id returned — the preview is still not live. ${homeHint}`,
        );
      }
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setError(err.warning);
      } else {
        reportApiError(err, setError, { fallback: "Apply failed", toast: true });
      }
    } finally {
      setBusy(null);
    }
  }

  return { submitRefine, onApplyToOdoo };
}
