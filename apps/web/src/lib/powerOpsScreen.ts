/**
 * UI-S-31 Power Ops screen logic and copy.
 * Pure helpers. No React. Test run before Run; what / why / next for empty and error.
 * Honesty for destructive recipes: phrase confirm, no auto-undo claim.
 */

export const PAGE_TITLE = "Power Ops";
export const PAGE_DESCRIPTION =
  "Ready-made bulk jobs that work like Odoo.sh scripts, including on Odoo Online when it allows. Always test run first. Changes need the risk phrase.";
export const PRIMARY_CTA = "Run recipe";
export const DRY_RUN_CTA = "Test run";
export const CONFIRM_PHRASE = "I understand the risks";

export const POWER_OPS_STEPS = ["Recipe", "Configure", "Test run", "Run"] as const;
export type PowerOpsStepLabel = (typeof POWER_OPS_STEPS)[number];
export type PowerOpsStepIndex = 1 | 2 | 3 | 4;

export type PowerOpsGuide = { title: string; why: string; next: string };

export type PowerOpsErrorContext =
  | "load"
  | "probe"
  | "dry_run"
  | "run"
  | "domain"
  | "blocked";

/** Strip em / en dashes from UI copy (playbook §0 law 9). */
export function sanitizePowerOpsCopy(text: string): string {
  return text.replace(/[\u2014\u2013]/g, "-");
}

export function isDangerRecipe(recipe: {
  id: string;
  destructive?: boolean;
  tags?: string[] | null;
}): boolean {
  if (recipe.destructive === true) return true;
  const tags = (recipe.tags ?? []).map((t) => t.toLowerCase());
  if (tags.some((t) => t.includes("danger") || t.includes("destructive"))) return true;
  const id = recipe.id.toLowerCase();
  return id.includes("purge") || id.includes("delete") || id.includes("unlink");
}

export function emptyPowerOpsGuide(): PowerOpsGuide {
  return {
    title: "No Power Ops recipes yet",
    why: "Stock recipes come from this connection's major and installed modules. A bare base database may list none until account or other apps are present.",
    next: "Re-probe the connection, or install the modules a recipe needs, then open Power Ops again.",
  };
}

export function idlePowerOpsGuide(): PowerOpsGuide {
  return {
    title: "Pick a recipe, then test run",
    why: "Run recipe stays locked until a test run succeeds for the same recipe, model, and domain. Destructive recipes still need the risk phrase.",
    next: "Select a recipe, set model and domain, then Test run. Read the counts before Run recipe.",
  };
}

export function powerOpsHonestyGuide(): PowerOpsGuide {
  return {
    title: "Test run never writes. Run is live.",
    why: "Successful steps stay applied even when later steps fail. Rollback may be incomplete for unlinks and posted moves.",
    next: "Test run first. For danger-zone recipes, confirm with the risk phrase only when the counts look right.",
  };
}

export function blockedRecipeGuide(opts: {
  blockReason: string;
  minMajor?: number | null;
  major?: number | null;
}): PowerOpsGuide {
  const needsMajor = opts.blockReason.startsWith("needs");
  return {
    title: "This recipe is blocked on this connection",
    why: needsMajor
      ? `This recipe needs Odoo major >=${opts.minMajor ?? "?"}. Connected major: ${opts.major ?? "unknown (re-probe)"}.`
      : opts.blockReason,
    next: needsMajor
      ? "Pick another recipe, or connect an instance on a supported major."
      : "Install the missing module on this database, re-probe, then try again.",
  };
}

export function partialFailureGuide(opts: {
  processed: number;
  succeeded: number;
  failed: number;
  dryRun: boolean;
}): PowerOpsGuide | null {
  if (opts.failed <= 0) return null;
  if (opts.dryRun) {
    return {
      title: `Test run previewed ${opts.failed} failure${opts.failed === 1 ? "" : "s"}`,
      why: `${opts.succeeded} of ${opts.processed} step${opts.processed === 1 ? "" : "s"} would succeed. Nothing was written.`,
      next: "Tighten the domain or fix the failing records, then Test run again before Run recipe.",
    };
  }
  return {
    title: `Finished with ${opts.failed} failure${opts.failed === 1 ? "" : "s"}`,
    why: `${opts.succeeded} of ${opts.processed} step${opts.processed === 1 ? "" : "s"} succeeded. Failed steps were not rolled back with the successes.`,
    next: "Read the per-step log, fix those records, then test run and run only what still needs work.",
  };
}

export function powerOpsErrorGuide(
  context: PowerOpsErrorContext,
  rawMessage?: string,
): PowerOpsGuide {
  const detail = (rawMessage || "").trim();
  const m = detail.toLowerCase();
  const classifiedWhy = (): string | null => {
    if (/timed? ?out|timeout|took too long|\b50[34]\b/.test(m)) {
      return "The Ingenium API or this Odoo connection took too long to answer.";
    }
    if (/failed to fetch|network|econn|unreachable|could not reach|offline/.test(m)) {
      return "Ingenium could not reach its API or this Odoo connection.";
    }
    if (/\b40[13]\b|permission|access denied|not allowed|forbidden/.test(m)) {
      return "The Odoo user on this connection lacks the rights for that step.";
    }
    if (/invalid domain|domain must|json/.test(m)) {
      return "The domain JSON did not parse as an Odoo domain list.";
    }
    if (/confirm|phrase|advanced/.test(m)) {
      return "Live run needs the advanced confirmation flag and the exact risk phrase.";
    }
    return null;
  };
  const whyOr = (fallback: string) => classifiedWhy() || fallback;

  switch (context) {
    case "probe":
      return {
        title: "Could not re-probe this connection",
        why: whyOr("The capability probe did not finish for this instance."),
        next: "Check Connect, then Re-probe connection once the API answers.",
      };
    case "dry_run":
      return {
        title: "Test run did not finish",
        why: whyOr("The connection refused the preview, or the recipe is blocked on this major."),
        next: "Fix the domain or pick an available recipe, then Test run again. No records were written.",
      };
    case "run":
      return {
        title: "Recipe run did not finish",
        why: whyOr("The connection refused the write, confirmation failed, or the request timed out."),
        next: "Review the step log. Successful steps are not auto-undone. Retry only what failed.",
      };
    case "domain":
      return {
        title: "Domain is not valid JSON",
        why: whyOr("Power Ops expects an Odoo domain list, for example []."),
        next: "Fix the domain field, then Test run again.",
      };
    case "blocked":
      return {
        title: "Recipe blocked on this connection",
        why: whyOr("Major or module requirements are not met."),
        next: "Pick another recipe, or install the required module and re-probe.",
      };
    case "load":
    default:
      return {
        title: "Power Ops did not load",
        why: whyOr("The Ingenium API or this Odoo connection did not answer in time."),
        next: "Reload once the API is up, or open Connect to check the instance.",
      };
  }
}

export function powerOpsStepFromState(opts: {
  recipeCount: number;
  hasRecipe: boolean;
  hasDryRun: boolean;
  hasWriteResult: boolean;
}): PowerOpsStepIndex {
  if (opts.recipeCount <= 0) return 1;
  if (!opts.hasRecipe) return 1;
  if (!opts.hasDryRun && !opts.hasWriteResult) return 2;
  if (opts.hasWriteResult) return 4;
  return 3;
}

export function runUnlockReason(opts: {
  selectedBlocked: boolean;
  canExecute: boolean;
}): string | null {
  if (opts.selectedBlocked) return "This recipe is blocked on this connection.";
  if (!opts.canExecute) {
    return "Run recipe unlocks after a successful test run with the same recipe, model, and domain.";
  }
  return null;
}
