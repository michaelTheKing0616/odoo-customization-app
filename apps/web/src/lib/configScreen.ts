/**
 * UI-S-36 Instance Config screen logic and copy.
 * Pure helpers. No React. Test run before Save/Apply; what / why / next for empty and error.
 * Honesty: test run never writes; live apply needs the risk phrase.
 */

export const PAGE_TITLE = "Instance Config";
export const PAGE_DESCRIPTION =
  "Recipe Command Center for Day-1, numbering, apps, allowlisted settings, and master packs. Test run first. Writes need the risk phrase.";
export const PRIMARY_CTA = "Save the setting";
export const APPLY_CTA = "Apply";
export const DRY_RUN_CTA = "Test run";
export const CONFIRM_PHRASE = "I understand the risks";

export const CONFIG_STEPS = ["Recipes", "Configure", "Test run", "Save"] as const;
export type ConfigStepLabel = (typeof CONFIG_STEPS)[number];
export type ConfigStepIndex = 1 | 2 | 3 | 4;

export type ConfigGuide = { title: string; why: string; next: string };

export type ConfigErrorContext =
  | "load"
  | "dry_run"
  | "apply"
  | "settings"
  | "atlas"
  | "panel";

export type ConfigPanelId =
  | "home"
  | "day1"
  | "numbering"
  | "apps-pack"
  | "settings-board"
  | "multi-company"
  | "master-packs";

/** Strip em / en dashes from UI copy (playbook section 0 law 9). */
export function sanitizeConfigCopy(text: string): string {
  return text.replace(/[\u2014\u2013]/g, "-");
}

export function emptyConfigGuide(): ConfigGuide {
  return {
    title: "No config recipes yet",
    why: "The Command Center loads recipe cards from this connection. An empty catalog means the API did not return Day-1, numbering, or apps packs.",
    next: "Reload once the API answers, or open Connect to check this instance.",
  };
}

export function idleConfigGuide(): ConfigGuide {
  return {
    title: "Pick a recipe, then test run",
    why: "Save the setting and Apply stay locked until a test run succeeds for the same panel and values. Live writes still need the risk phrase.",
    next: "Open a recipe, review the fields, then Test run. Read the plan before Save the setting or Apply.",
  };
}

export function configHonestyGuide(): ConfigGuide {
  return {
    title: "Test run never writes. Save and Apply are live.",
    why: "A successful test run only previews steps. Apply writes on the connected Odoo instance. Some steps are hard to reverse without a snapshot.",
    next: "Test run first. Confirm with the risk phrase only when the plan looks right.",
  };
}

export function appliedConfigGuide(label: string): ConfigGuide {
  return {
    title: `${label} applied`,
    why: "Writes ran on the connected Odoo instance. Successful steps are not auto-undone.",
    next: "Verify in Odoo, or open another recipe. Re-dry-run if you change fields before the next apply.",
  };
}

export function configErrorGuide(
  context: ConfigErrorContext,
  rawMessage?: string,
): ConfigGuide {
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
    if (/confirm|phrase|advanced/.test(m)) {
      return "Live apply needs the advanced confirmation flag and the exact risk phrase.";
    }
    if (/allowlist|not allowlisted|unknown key/.test(m)) {
      return "One or more keys are outside the allowlisted res.config.settings set.";
    }
    return null;
  };
  const whyOr = (fallback: string) => classifiedWhy() || fallback;

  switch (context) {
    case "dry_run":
      return {
        title: "Test run did not finish",
        why: whyOr("The connection refused the preview, or the recipe inputs are incomplete."),
        next: "Fix the fields, then Test run again. No records were written.",
      };
    case "apply":
      return {
        title: "Apply did not finish",
        why: whyOr("The connection refused the write, confirmation failed, or the request timed out."),
        next: "Review the plan preview. Successful steps are not auto-undone. Retry only what failed.",
      };
    case "settings":
      return {
        title: "Settings board did not save",
        why: whyOr("Allowlisted settings refused the patch, or confirmation failed."),
        next: "Check the allowlist keys, Test run again, then Save the setting with the risk phrase.",
      };
    case "atlas":
      return {
        title: "Config Atlas did not load",
        why: whyOr("The atlas catalog or Batch OS recipes did not answer in time."),
        next: "Reload the atlas once the API is up, or open Connect to check the instance.",
      };
    case "panel":
      return {
        title: "Recipe panel did not load",
        why: whyOr("Catalog data for this panel did not load from the API."),
        next: "Go back to Command Center, then open the recipe again once the API answers.",
      };
    case "load":
    default:
      return {
        title: "Instance Config did not load",
        why: whyOr("The Ingenium API or this Odoo connection did not answer in time."),
        next: "Reload once the API is up, or open Connect to check the instance.",
      };
  }
}

export function configStepFromState(opts: {
  panel: ConfigPanelId;
  recipeCount: number;
  hasDryRun: boolean;
  hasWriteResult: boolean;
}): ConfigStepIndex {
  if (opts.panel === "home") {
    return opts.recipeCount <= 0 ? 1 : 1;
  }
  if (opts.hasWriteResult) return 4;
  if (opts.hasDryRun) return 3;
  return 2;
}

export function applyUnlockReason(opts: {
  canApply: boolean;
  panel: ConfigPanelId;
}): string | null {
  if (opts.panel === "home") return null;
  if (!opts.canApply) {
    return opts.panel === "settings-board"
      ? "Save the setting unlocks after a successful test run with the same values."
      : "Apply unlocks after a successful test run with the same panel and values.";
  }
  return null;
}

export function planHonestyLabel(dryRun: boolean): string {
  return dryRun
    ? "Test run plan (no writes)"
    : "Applied plan (writes applied)";
}

export function primaryCtaForPanel(panel: ConfigPanelId): string {
  if (panel === "settings-board") return PRIMARY_CTA;
  if (panel === "apps-pack") return "Install pack";
  if (panel === "multi-company") return "Create company";
  if (panel === "numbering" || panel === "master-packs") return "Apply pack";
  if (panel === "day1") return APPLY_CTA;
  return APPLY_CTA;
}

export function applyKeyForPanel(
  panel: ConfigPanelId,
  fingerprint: string,
): string {
  return `${panel}|${fingerprint}`;
}

export function configSessionBadge(step: ConfigStepIndex): {
  label: string;
  variant: "default" | "warning" | "success" | "info" | "danger";
} {
  const labels = ["Recipes", "Configure", "Test run", "Save"] as const;
  const i = Math.max(1, Math.min(4, step)) - 1;
  const variants = ["default", "info", "warning", "success"] as const;
  return { label: labels[i], variant: variants[i] };
}

/** Alias used by the ConfigStateGuide component. */
export type ConfigStateGuide = ConfigGuide;
