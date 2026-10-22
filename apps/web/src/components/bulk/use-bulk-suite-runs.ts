"use client";

import { api, ConfirmationRequiredError } from "@/lib/api";
import { changeApi } from "@/lib/api/suite";

/** A5: record types the shared Run sheet (suite > Change records > Edit a field) handles today. */
export const RUN_SHEET_EDIT_MODELS = new Set(["sale.order", "purchase.order", "crm.lead", "res.partner", "product.template", "project.task"]);
import { CONFIRM_PHRASE, parseSelection } from "./bulk-helpers";
import type { BulkSuiteState } from "./use-bulk-suite-state";

export function useBulkSuiteRuns(s: BulkSuiteState) {
  const { connectionId } = s;

  async function discover() {
    s.setDiscoverBusy(true);
    s.setError(null);
    s.setButtons([]);
    s.setMethod("");
    try {
      const res = await api.bulkTransitions(connectionId, s.model.trim());
      s.setButtons(res.buttons);
      const firstSafe = res.buttons.find((b) => b.bulk_safe);
      if (firstSafe) s.setMethod(firstSafe.name);
      else if (res.buttons[0]) s.setMethod(res.buttons[0].name);
      s.setNotice(
        res.buttons.length
          ? `Discovered ${res.buttons.length} object button(s) on form view.`
          : "No object buttons found on the primary form view.",
      );
    } catch (err) {
      s.setError(err instanceof Error ? err.message : "Discovery failed");
    } finally {
      s.setDiscoverBusy(false);
    }
  }

  async function continueSampleRun() {
    if (!s.result?.run_id) return;
    s.setRunControlBusy(true);
    s.setError(null);
    try {
      const res = await api.bulkRunContinue(connectionId, s.result.run_id);
      s.setResult(res);
      s.setNotice(res.message);
    } catch (err) {
      s.setError(err instanceof Error ? err.message : "Continue failed");
    } finally {
      s.setRunControlBusy(false);
    }
  }

  async function abortSampleRun() {
    if (!s.result?.run_id) return;
    s.setRunControlBusy(true);
    s.setError(null);
    try {
      const res = await api.bulkRunAbort(connectionId, s.result.run_id);
      s.setResult(res);
      s.setNotice(res.message);
    } catch (err) {
      s.setError(err instanceof Error ? err.message : "Abort failed");
    } finally {
      s.setRunControlBusy(false);
    }
  }

  async function run(dryRun: boolean, phrase?: string) {
    if (!s.method.trim()) {
      s.setError("Pick a discovered transition method.");
      return;
    }
    if (!dryRun && s.selectedButton && !s.selectedButton.bulk_safe) {
      s.setError(`Method is not bulk-safe: ${s.selectedButton.reason}`);
      return;
    }
    s.setBusy(true);
    s.setError(null);
    const progress_run_id = s.beginProgressRun("bulk");
    try {
      const selection = parseSelection(s.selectionMode, s.domainText, s.idsText);
      const res = await api.bulkTransitionRun(connectionId, {
        model: s.model.trim(),
        method: s.method.trim(),
        ...selection,
        dry_run: dryRun,
        progress_run_id,
        ...(dryRun
          ? {}
          : { confirm_advanced: true, confirm_phrase: phrase || CONFIRM_PHRASE }),
      });
      s.setResult(res);
      s.setNotice(res.message);
      s.setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        s.setConfirmMode("transition");
        s.setConfirmOpen(true);
        s.setError(err.warning);
      } else {
        s.setError(err instanceof Error ? err.message : "Run failed");
      }
    } finally {
      s.setBusy(false);
    }
  }

  async function runMassEdit(dryRun: boolean, phrase?: string) {
    s.setBusy(true);
    s.setError(null);
    try {
      let values: Record<string, unknown>;
      try {
        values = JSON.parse(s.valuesText) as Record<string, unknown>;
        if (!values || typeof values !== "object" || Array.isArray(values)) {
          throw new Error("values must be a JSON object");
        }
      } catch {
        throw new Error('Invalid values JSON - e.g. {"x_name": "New title"}');
      }
      const selection = parseSelection(s.selectionMode, s.domainText, s.idsText);
      const fieldNames = Object.keys(values);
      if (!dryRun && fieldNames.length === 1 && RUN_SHEET_EDIT_MODELS.has(s.model.trim())) {
        // A5: real writes go through the shared Run sheet (check, approval rule, money guard, undo).
        const batch = await changeApi.create(connectionId, {
          tool: "edit",
          model: s.model.trim(),
          name: `Edit ${fieldNames[0]} (from Bulk tools)`,
          domain: selection.domain ?? [],
          ids: selection.ids ?? [],
          change: { field: fieldNames[0], value: values[fieldNames[0]] },
        });
        s.setConfirmOpen(false);
        s.setNotice("Opening the Run sheet: check, approval and undo happen there.");
        window.location.assign(`/connections/${connectionId}/suite/change/edit?batch=${encodeURIComponent(batch.id)}`);
        return;
      }
      const res = await api.bulkMassEdit(connectionId, {
        model: s.model.trim(),
        values,
        ...selection,
        dry_run: dryRun,
        ...(dryRun
          ? {}
          : { confirm_advanced: true, confirm_phrase: phrase || CONFIRM_PHRASE }),
      });
      s.setResult(res);
      s.setNotice(res.message);
      s.setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        s.setConfirmMode("mass_edit");
        s.setConfirmOpen(true);
        s.setError(err.warning);
      } else {
        s.setError(err instanceof Error ? err.message : "Mass edit failed");
      }
    } finally {
      s.setBusy(false);
    }
  }

  async function scanDedupe() {
    s.setBusy(true);
    s.setError(null);
    s.setScanResult(null);
    try {
      const match_fields = s.matchFieldsText
        .split(/[\s,]+/)
        .map((part) => part.trim())
        .filter(Boolean);
      if (!match_fields.length) throw new Error("Enter at least one match field");
      const res = await api.bulkDedupeScan(connectionId, {
        model: s.model.trim(),
        match_fields,
        mode: s.dedupeMode,
      });
      s.setScanResult(res);
      s.setSelectedGroupIdx(0);
      if (res.groups[0]?.records[0]) {
        s.setWinnerId(res.groups[0].records[0].id);
      }
      s.setNotice(res.message);
    } catch (err) {
      s.setError(err instanceof Error ? err.message : "Scan failed");
    } finally {
      s.setBusy(false);
    }
  }

  async function mergeDedupe(dryRun: boolean, phrase?: string) {
    if (s.winnerId == null || !s.loserIds.length) {
      s.setError("Scan duplicate groups and pick a winner first.");
      return;
    }
    s.setBusy(true);
    s.setError(null);
    try {
      const res = await api.bulkDedupeMerge(connectionId, {
        model: s.model.trim(),
        winner_id: s.winnerId,
        loser_ids: s.loserIds,
        dry_run: dryRun,
        archive_or_delete: "archive",
        ...(dryRun
          ? {}
          : { confirm_advanced: true, confirm_phrase: phrase || CONFIRM_PHRASE }),
      });
      s.setResult(res);
      s.setNotice(res.message);
      s.setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        s.setConfirmMode("dedupe_merge");
        s.setConfirmOpen(true);
        s.setError(err.warning);
      } else {
        s.setError(err instanceof Error ? err.message : "Merge failed");
      }
    } finally {
      s.setBusy(false);
    }
  }

  return {
    discover,
    continueSampleRun,
    abortSampleRun,
    run,
    runMassEdit,
    scanDedupe,
    mergeDedupe,
  };
}

export type BulkSuiteRuns = ReturnType<typeof useBulkSuiteRuns>;
