/**
 * UI-S-35 Script Runner screen logic and copy.
 * Pure helpers. No React.
 * Honesty (Option A for Python): there is no test run. Confirm phrase then live RPC.
 * Sandbox = subprocess + import allowlist, not a preview.
 */

export const PAGE_TITLE = "Script Runner";
export const PAGE_DESCRIPTION =
  "Run Python on this connection inside a sandboxed subprocess. There is no test run. A write waits for the confirm phrase, then uses real Odoo RPC.";
export const PRIMARY_CTA = "Run script";
export const CONFIRM_PHRASE = "I understand the risks";

export const SCRIPT_RUNNER_STEPS = ["Compose", "Confirm", "Run"] as const;
export type ScriptRunnerStepLabel = (typeof SCRIPT_RUNNER_STEPS)[number];
export type ScriptRunnerStepIndex = 1 | 2 | 3;

export type ScriptRunnerGuide = { title: string; why: string; next: string };

export type ScriptRunnerErrorContext =
  | "load"
  | "save"
  | "run"
  | "abort"
  | "observer";

/** Strip em / en dashes from UI copy (playbook law 9). */
export function sanitizeScriptRunnerCopy(text: string): string {
  return text.replace(/[\u2014\u2013]/g, "-");
}

export function scriptRunnerStepFromState(opts: {
  hasScript: boolean;
  confirmOpen: boolean;
  busy: boolean;
  hasResult: boolean;
}): ScriptRunnerStepIndex {
  if (opts.busy || opts.hasResult) return 3;
  if (opts.confirmOpen) return 2;
  if (opts.hasScript) return 1;
  return 1;
}

export function scriptRunnerHonestyGuide(): ScriptRunnerGuide {
  return {
    title: "No test run for Python. Confirm then live RPC.",
    why: "The sandbox blocks filesystem and network imports. It does not preview writes. After the confirm phrase, the script uses this connection's Odoo credentials for real.",
    next: "Read the limits, type the risk phrase only when you mean to write, then check the journal if a snapshot was taken.",
  };
}

export function emptyScriptRunnerGuide(): ScriptRunnerGuide {
  return {
    title: "No run yet",
    why: "Outcomes, write counts, and snapshot ids appear here after a script finishes.",
    next: "Load a template or write Python, then Run script. Confirm the phrase before any write.",
  };
}

export function idleScriptRunnerGuide(): ScriptRunnerGuide {
  return {
    title: "Compose the script, then confirm",
    why: "Run script opens the risk dialog. Nothing reaches Odoo until you type the confirm phrase.",
    next: "Use a template or the library, fix any line warnings, then Run script.",
  };
}

export function observerScriptRunnerGuide(): ScriptRunnerGuide {
  return {
    title: "Observer mode blocks writes",
    why: "This connection is unlocked for reads only. A mutating script would be refused at the gate.",
    next: "Unlock write mode on the connection, then return here to run the script.",
  };
}

export function failedScriptRunnerGuide(summary: string): ScriptRunnerGuide {
  const detail = sanitizeScriptRunnerCopy((summary || "The script failed.").slice(0, 400));
  return {
    title: "The last run failed",
    why: detail,
    next: "Fix the script from the console or the failure line, then Run script again. Open the journal if a snapshot was taken.",
  };
}

export function succeededScriptRunnerGuide(opts: {
  writeCount: number;
  snapshotId?: string | null;
}): ScriptRunnerGuide {
  const writes = opts.writeCount ?? 0;
  return {
    title: "Script finished",
    why:
      writes === 0
        ? "No writes were recorded for this run."
        : `${writes} write${writes === 1 ? "" : "s"} recorded on this connection.`,
    next: opts.snapshotId
      ? `Snapshot ${opts.snapshotId} was taken before the write. Open the journal to restore a view, automation, or server action. Record writes are only partly recoverable. Dropped columns cannot be restored.`
      : "Review the console output. Save the script to the library if you will reuse it.",
  };
}

export function scriptRunnerErrorGuide(
  context: ScriptRunnerErrorContext,
  rawMessage?: string,
): ScriptRunnerGuide {
  const detail = sanitizeScriptRunnerCopy((rawMessage || "").trim());
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
    if (/confirm|phrase|risk/.test(m)) {
      return "The confirm phrase did not match, or confirmation was required before a write.";
    }
    return null;
  };
  const why = classifiedWhy() || detail || "Something went wrong while talking to Ingenium or Odoo.";

  switch (context) {
    case "load":
      return {
        title: "Could not load Script Runner",
        why,
        next: "Check the connection, then retry. If it keeps failing, Diagnose with Expert.",
      };
    case "save":
      return {
        title: "Could not save the script",
        why,
        next: "Enter a name, check the connection, then Save to library again.",
      };
    case "abort":
      return {
        title: "Could not abort the run",
        why,
        next: "Wait for the job to finish, or retry Abort. Check the journal for the outcome.",
      };
    case "observer":
      return {
        title: "Observer mode blocked the run",
        why,
        next: "Unlock write mode on this connection, then Run script again.",
      };
    case "run":
    default:
      return {
        title: "Could not run the script",
        why,
        next: "Fix the script or the connection, confirm the phrase, then Run script again.",
      };
  }
}

export const RESTORE_NOTE =
  "Open the journal and restore a view, automation, or server action if this script changed one. This snapshot does not undo record writes. Dropped columns cannot be restored.";

export const SANDBOX_LIMITS =
  "The script cannot use the filesystem or open its own network. Imports stay on the allowlist. A write waits for the confirm phrase, then saves a snapshot. Unlink on users, companies, XML ids, and protected database parameters is refused.";

export function resultHonestyLabel(succeeded: boolean): string {
  return succeeded
    ? "Run result (writes applied when reported)"
    : "Run result (no successful writes)";
}


export function scriptRunnerSessionBadge(step: ScriptRunnerStepIndex): {
  label: string;
  variant: "default" | "warning" | "success" | "info" | "danger";
} {
  if (step === 3) return { label: "Run", variant: "info" };
  if (step === 2) return { label: "Confirm", variant: "warning" };
  return { label: "Compose", variant: "default" };
}
