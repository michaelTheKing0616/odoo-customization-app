/**
 * UI-S-38 Change Journal screen logic and copy.
 * Pure helpers. No React.
 * Primary CTA: Roll back. Honesty for partial restore and audit replay.
 * Chain verify once T5A-03 ships (called out, not claimed as live).
 */

export const PAGE_TITLE = "History";
export const PAGE_DESCRIPTION =
  "Timeline of snapshots, audits, and health sweeps on this connection. Roll back a reversible snapshot. Batch tabs create drafts in Accounting; they do not replace this restore path.";
export const PRIMARY_CTA = "Roll back";
export const REFRESH_CTA = "Refresh timeline";

export const JOURNAL_STEPS = ["Timeline", "Inspect", "Roll back"] as const;
export type JournalStepLabel = (typeof JOURNAL_STEPS)[number];
export type JournalStepIndex = 1 | 2 | 3;

export type JournalGuide = { title: string; why: string; next: string };

export type JournalErrorContext =
  | "load"
  | "rollback"
  | "refresh"
  | "batch";

export type JournalTab = "timeline" | "batch" | "invoices" | "orders" | "master";
export type JournalTimelineFilter = "all" | "snapshot" | "audit" | "health";

/** Strip em / en dashes from UI copy (playbook law 9). */
export function sanitizeJournalCopy(text: string): string {
  return text.replace(/[\u2014\u2013]/g, "-");
}

export function journalHonestyGuide(): JournalGuide {
  return {
    title: "Roll back is partial for some changes. Audit is replay, not undo.",
    why: "Snapshots restore views, automations, and server actions when marked reversible. Record writes and dropped columns stay. Audit rows replay what happened; they do not reverse it. Chain verify for restore integrity lands with T5A-03 and is not claimed here yet.",
    next: "Filter to Snapshots, read the reversibility badge, then Roll back only when the label matches what you need to restore.",
  };
}

export function emptyJournalGuide(): JournalGuide {
  return {
    title: "No journal entries yet",
    why: "Snapshots appear after a risky write takes a restore point. Audits and health sweeps show up once those flows run on this connection.",
    next: "Make a change that snapshots, run a health sweep, or Refresh timeline once activity exists.",
  };
}

export function idleJournalGuide(): JournalGuide {
  return {
    title: "Inspect an entry, then roll back if it is reversible",
    why: "Roll back is the teal primary on reversible snapshots. Audit and health rows stay read-only.",
    next: "Open Snapshots filter when restoring. Read the badge before you confirm the restore.",
  };
}

export function partialRollbackGuide(): JournalGuide {
  return {
    title: "This snapshot is only partly reversible",
    why: "Some fields or side effects may remain after restore. Dropped columns cannot be restored.",
    next: "Roll back if the rest of the snapshot still helps, or fix the leftover fields in Odoo by hand.",
  };
}

export function irreversibleGuide(): JournalGuide {
  return {
    title: "Roll back is disabled for this snapshot",
    why: "Ingenium marked this restore point as not reversible. Undo would be unsafe or incomplete.",
    next: "Leave it as a record, or rebuild the change from Draft Studio / Code Studio with a fresh snapshot first.",
  };
}

export function rollbackSuccessGuide(label: string, restoredId?: string | number): JournalGuide {
  const name = sanitizeJournalCopy((label || "Snapshot").slice(0, 120));
  return {
    title: "Restore finished",
    why: restoredId != null
      ? `${name} restored as #${restoredId}. Check the live resource matches what you expected.`
      : `${name} was restored. Check the live resource matches what you expected.`,
    next: "Refresh timeline. If something still looks wrong, open the resource and fix leftovers by hand. Dropped columns stay gone.",
  };
}

export function auditReplayGuide(): JournalGuide {
  return {
    title: "Audit rows are honest replay",
    why: "Each audit line is a request that already happened: method, path, status, and optional mutation detail. Replaying the log does not undo the write.",
    next: "Use the path and detail to find the tool that wrote, then take a new snapshot before you change it again.",
  };
}

export function healthSweepGuide(brokenCount: number): JournalGuide {
  if (brokenCount > 0) {
    return {
      title: `${brokenCount} broken artifact${brokenCount === 1 ? "" : "s"} in this sweep`,
      why: "A health sweep compared expected artifacts to what Odoo returned after a version or module change.",
      next: "Open each deep link, fix or remove the broken artifact, then run another sweep.",
    };
  }
  return {
    title: "Health sweep completed clean",
    why: "No broken artifacts were reported for this run.",
    next: "Keep the timeline for audit. Re-run after the next upgrade or module install.",
  };
}

export function journalErrorGuide(
  context: JournalErrorContext,
  rawMessage?: string,
): JournalGuide {
  const detail = sanitizeJournalCopy((rawMessage || "").trim());
  const m = detail.toLowerCase();
  const classifiedWhy = (): string | null => {
    if (/timed? ?out|timeout|took too long|\b50[34]\b/.test(m)) {
      return "The Ingenium API or this Odoo connection took too long to answer.";
    }
    if (/failed to fetch|network|econn|unreachable|could not reach|offline/.test(m)) {
      return "Ingenium could not reach its API or this Odoo connection.";
    }
    if (/\b40[13]\b|permission|access denied|not allowed|forbidden|observer/.test(m)) {
      return "This connection refused the action. Write mode or permissions may block it.";
    }
    if (/reversib|snapshot|rollback|restore/.test(m)) {
      return "The snapshot could not be restored, or it is marked not reversible.";
    }
    return null;
  };
  const why = classifiedWhy() || detail || "Something went wrong while talking to Ingenium or Odoo.";

  switch (context) {
    case "rollback":
      return {
        title: "Roll back did not finish",
        why,
        next: "Refresh the timeline, confirm the snapshot is still reversible, then try Roll back again. Diagnose with Expert if it repeats.",
      };
    case "refresh":
      return {
        title: "Could not refresh the timeline",
        why,
        next: "Check the connection, then Refresh timeline once the API answers.",
      };
    case "batch":
      return {
        title: "Journal batch step failed",
        why,
        next: "Fix the CSV map or balance errors, Test run again, then Apply drafts only when the preview is clean.",
      };
    case "load":
    default:
      return {
        title: "Change journal did not load",
        why,
        next: "Reload once the API is up, or open Connect to check the instance.",
      };
  }
}

export function journalStepFromState(opts: {
  entryCount: number;
  hasSelection: boolean;
  rollbackDone: boolean;
  tab: JournalTab;
}): JournalStepIndex {
  if (opts.tab !== "timeline") return 1;
  if (opts.entryCount <= 0) return 1;
  if (opts.rollbackDone) return 3;
  if (opts.hasSelection) return 2;
  return 1;
}

export function reversibilityLabel(reversible: string): "yes" | "partial" | "none" {
  if (reversible === "yes") return "yes";
  if (reversible === "partial") return "partial";
  return "none";
}

export function reversibilityCopy(reversible: string): string {
  const kind = reversibilityLabel(reversible);
  if (kind === "yes") return "Fully reversible";
  if (kind === "partial") {
    return "Partially reversible: some fields or side effects may remain. Dropped columns cannot be restored.";
  }
  return "Not reversible: Roll back is disabled for this snapshot.";
}

export function canRollback(reversible: string): boolean {
  const kind = reversibilityLabel(reversible);
  return kind === "yes" || kind === "partial";
}

export const BATCH_HONESTY =
  "Test run checks balance and resolves accounts via public RPC. Apply creates draft account.move rows. Optional post is L2 and needs the risk phrase. Preview is not posted.";

export const CHAIN_VERIFY_NOTE =
  "Tamper-proof checks on this history are coming later. Today it shows what was saved, not a verified chain.";

export function journalSessionBadge(step: JournalStepIndex): {
  label: string;
  variant: "default" | "warning" | "success" | "info" | "danger";
} {
  const labels = ["Timeline", "Inspect", "Roll back"] as const;
  const i = Math.max(1, Math.min(3, step)) - 1;
  const variants = ["default", "info", "warning"] as const;
  return { label: labels[i], variant: variants[i] };
}

/** Alias used by the JournalStateGuide component. */
export type JournalStateGuide = JournalGuide;
