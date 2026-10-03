"use client";

import { api, ConfirmationRequiredError } from "@/lib/api";
import { CONFIRM_PHRASE, parseIdList, parseSelection } from "./bulk-helpers";
import type { BulkSuiteState } from "./use-bulk-suite-state";

export function useBulkSuiteAccess(s: BulkSuiteState) {
  const { connectionId } = s;

  async function probeActivities() {
    s.setBusy(true);
    s.setError(null);
    try {
      const res = await api.bulkActivitiesProbe(connectionId, s.model.trim());
      s.setActivityProbe(res.message);
      s.setNotice(res.message);
    } catch (err) {
      s.setError(err instanceof Error ? err.message : "Activity probe failed");
    } finally {
      s.setBusy(false);
    }
  }

  async function runActivities(dryRun: boolean, phrase?: string) {
    if (!s.activityTypeId) {
      s.setError("Pick an activity type.");
      return;
    }
    s.setBusy(true);
    s.setError(null);
    try {
      const selection = parseSelection(s.selectionMode, s.domainText, s.idsText);
      const res = await api.bulkActivities(connectionId, {
        model: s.model.trim(),
        ...selection,
        activity_type_id: Number(s.activityTypeId),
        summary: s.activitySummary,
        date_deadline: s.activityDeadline || new Date().toISOString().slice(0, 10),
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
        s.setConfirmMode("activities");
        s.setConfirmOpen(true);
        s.setError(err.warning);
      } else {
        s.setError(err instanceof Error ? err.message : "Bulk activities failed");
      }
    } finally {
      s.setBusy(false);
    }
  }

  async function previewSecurity() {
    s.setBusy(true);
    s.setError(null);
    try {
      const res = await api.bulkSecurityPreview(connectionId, {
        user_ids: parseIdList(s.securityUserIds, "user"),
        group_ids: s.securityMode === "offboard" ? [] : parseIdList(s.securityGroupIds, "group"),
        mode: s.securityMode,
        deactivate: s.securityOffboardDeactivate,
      });
      s.setSecurityPreview(res);
      s.setNotice(res.message);
    } catch (err) {
      s.setError(err instanceof Error ? err.message : "Security preview failed");
    } finally {
      s.setBusy(false);
    }
  }

  async function applySecurity(dryRun: boolean, phrase?: string) {
    if (!dryRun && !s.securityPreview) {
      s.setError("Run security preview before apply.");
      return;
    }
    s.setBusy(true);
    s.setError(null);
    try {
      const res = await api.bulkSecurityApply(connectionId, {
        user_ids: parseIdList(s.securityUserIds, "user"),
        group_ids: s.securityMode === "offboard" ? [] : parseIdList(s.securityGroupIds, "group"),
        mode: s.securityMode,
        deactivate: s.securityOffboardDeactivate,
        dry_run: dryRun,
        preview_acknowledged: dryRun || Boolean(s.securityPreview),
        ...(dryRun
          ? {}
          : { confirm_advanced: true, confirm_phrase: phrase || CONFIRM_PHRASE }),
      });
      s.setResult(res);
      s.setNotice(res.message);
      s.setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        s.setConfirmMode("security");
        s.setConfirmOpen(true);
        s.setError(err.warning);
      } else {
        s.setError(err instanceof Error ? err.message : "Security apply failed");
      }
    } finally {
      s.setBusy(false);
    }
  }

  async function runPortal(dryRun: boolean, phrase?: string) {
    s.setBusy(true);
    s.setError(null);
    try {
      const res = await api.bulkPortal(connectionId, {
        partner_ids: parseIdList(s.portalPartnerIds, "partner"),
        action: s.portalAction,
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
        s.setConfirmMode("portal");
        s.setConfirmOpen(true);
        s.setError(err.warning);
      } else {
        s.setError(err instanceof Error ? err.message : "Portal batch failed");
      }
    } finally {
      s.setBusy(false);
    }
  }

  async function runSendMessage(dryRun: boolean, phrase?: string) {
    if (!s.model.trim()) {
      s.setError("Select a model first.");
      return;
    }
    if (!s.sendBody.trim() && !s.sendTemplateId.trim()) {
      s.setError("Enter message body or a mail template id.");
      return;
    }
    s.setBusy(true);
    s.setError(null);
    try {
      const selection = parseSelection(s.selectionMode, s.domainText, s.idsText);
      const res = await api.bulkSendMessage(connectionId, {
        model: s.model,
        ...selection,
        body: s.sendBody.trim() || null,
        subject: s.sendSubject.trim() || null,
        mail_template_id: s.sendTemplateId.trim() ? Number(s.sendTemplateId) : null,
        dry_run: dryRun,
        ...(dryRun ? {} : { confirm_advanced: true, confirm_phrase: phrase || CONFIRM_PHRASE }),
      });
      s.setResult(res);
      s.setNotice(res.message);
      s.setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        s.setConfirmMode("send_message");
        s.setConfirmOpen(true);
        s.setError(err.warning);
      } else {
        s.setError(err instanceof Error ? err.message : "Send message failed");
      }
    } finally {
      s.setBusy(false);
    }
  }

  return {
    probeActivities,
    runActivities,
    previewSecurity,
    applySecurity,
    runPortal,
    runSendMessage,
  };
}

export type BulkSuiteAccess = ReturnType<typeof useBulkSuiteAccess>;
