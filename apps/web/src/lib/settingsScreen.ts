/**
 * UI-S-41 Settings (/settings) screen logic and copy.
 * Pure helpers. No React. Browser save is localStorage only; new keys shown once;
 * revoke is permanent. What / why / next for empty, idle, revealed, bootstrap, error.
 */

export const PAGE_TITLE = "API settings";
export const PAGE_DESCRIPTION =
  "Protect the customization API with an app API key, separate from Odoo credentials. Create keys here, keep one in this browser, and revoke what you no longer need.";
export const PRIMARY_CTA = "Create API key";
export const BOOTSTRAP_CTA = "Generate first API key";
export const SAVE_CTA = "Save in browser";
export const REVOKE_PHRASE = "revoke this key";

export const SETTINGS_STEPS = ["Status", "Keys", "Audit"] as const;
export type SettingsStepLabel = (typeof SETTINGS_STEPS)[number];
export type SettingsStepIndex = 1 | 2 | 3;

export type SettingsGuide = { title: string; why: string; next: string };

export type SettingsErrorContext =
  | "load"
  | "bootstrap"
  | "create"
  | "revoke"
  | "save"
  | "unlink";

/** Strip em / en dashes from UI copy (playbook section 0 law 9). */
export function sanitizeSettingsCopy(text: string): string {
  return text.replace(/[—–]/g, "-");
}

export function settingsStepFromState(opts: {
  hasStatus: boolean;
  keysListed: boolean;
  keyCount: number;
  revealed: boolean;
  auditHydrated: boolean;
}): SettingsStepIndex {
  if (opts.revealed || (opts.keysListed && opts.keyCount > 0)) return 2;
  if (opts.auditHydrated && opts.hasStatus && opts.keysListed) return 3;
  if (opts.hasStatus) return 1;
  return 1;
}

export function settingsHonestyGuide(): SettingsGuide {
  return {
    title: "Browser save stays on this device. New keys are shown once.",
    why: "Save in browser writes localStorage only. Created and bootstrap keys appear in a one-time reveal. Revoke permanently disables that key.",
    next: "Create or generate a key, copy it immediately, then Save in browser if this machine should call the API.",
  };
}

export function emptySettingsGuide(): SettingsGuide {
  return {
    title: "No API keys yet",
    why: "Auth is on, but this workspace has no active keys listed for the key stored in this browser.",
    next: "Name a key, then Create API key. Copy the value when it appears. It will not be shown again.",
  };
}

export function idleSettingsGuide(): SettingsGuide {
  return {
    title: "Create a key, then save it in this browser",
    why: "The customization API expects Authorization Bearer with an app key. Odoo login credentials are never used here.",
    next: "Create API key (or generate the first one), copy the reveal, then Save in browser. Open Trust and safety for the permission contract.",
  };
}

export function bootstrapSettingsGuide(): SettingsGuide {
  return {
    title: "No keys yet. Bootstrap can mint the first one.",
    why: "Auth is enabled and bootstrap is still available, so the API will accept a one-time first-key create without an existing Bearer token.",
    next: "Generate first API key, copy it immediately, then Save in browser. Bootstrap closes after the first key exists.",
  };
}

export function revealedSettingsGuide(): SettingsGuide {
  return {
    title: "Copy now. This value is shown once.",
    why: "Ingenium stores only a hash of the key. After you leave this screen, the full secret cannot be retrieved.",
    next: "Copy the key, then Save in browser on machines that should call the API. Revoke any key you no longer need.",
  };
}

export function savedBrowserGuide(cleared: boolean): SettingsGuide {
  if (cleared) {
    return {
      title: "Browser key cleared",
      why: "localStorage no longer holds an API key on this device. Server keys are unchanged.",
      next: "Paste a key and Save in browser when this machine should call the API again.",
    };
  }
  return {
    title: "API key saved in this browser",
    why: "The value lives in localStorage on this device only. It is sent as Authorization Bearer on API calls from this browser.",
    next: "Refresh status if needed. Revoke the key from the Keys list if this device should stop calling the API.",
  };
}

export function settingsErrorGuide(
  context: SettingsErrorContext,
  rawMessage?: string,
): SettingsGuide {
  const detail = sanitizeSettingsCopy((rawMessage || "").trim());
  const m = detail.toLowerCase();
  const classifiedWhy = (): string | null => {
    if (/timed? ?out|timeout|took too long|\b50[34]\b/.test(m)) {
      return "The Ingenium API took too long to answer.";
    }
    if (/failed to fetch|network|econn|unreachable|could not reach|offline/.test(m)) {
      return "This browser could not reach the Ingenium API.";
    }
    if (/\b40[13]\b|permission|access denied|not allowed|forbidden|unauthorized/.test(m)) {
      return "The current browser key lacks rights for that settings action.";
    }
    if (/bootstrap|already|first key/.test(m)) {
      return "Bootstrap is only available before the first key exists.";
    }
    return null;
  };
  const whyOr = (fallback: string) => classifiedWhy() || fallback;
  const detailSuffix = detail ? ` Detail: ${detail}` : "";

  switch (context) {
    case "bootstrap":
      return {
        title: "Could not generate the first API key",
        why: whyOr("Bootstrap refused, or a key already exists.") + detailSuffix,
        next: "Refresh status. If keys already exist, create a new one with Create API key instead.",
      };
    case "create":
      return {
        title: "Could not create an API key",
        why: whyOr("The API refused the create, or the browser key is missing.") + detailSuffix,
        next: "Check the browser key, fix the name, then Create API key again.",
      };
    case "revoke":
      return {
        title: "Could not revoke that key",
        why: whyOr("The API refused the revoke, or the key was already revoked.") + detailSuffix,
        next: "Refresh the Keys list, then retry revoke if the key is still active.",
      };
    case "save":
      return {
        title: "Could not save the browser key",
        why: whyOr("localStorage is blocked or unavailable in this browser.") + detailSuffix,
        next: "Allow site data for this origin, then Save in browser again.",
      };
    case "unlink":
      return {
        title: "Could not unlink that sign-in provider",
        why: whyOr("The account API refused the unlink.") + detailSuffix,
        next: "Retry unlink, or keep the provider linked if this account still needs it.",
      };
    case "load":
    default:
      return {
        title: "Could not load API settings",
        why: whyOr("The auth status or audit API did not answer.") + detailSuffix,
        next: "Refresh the page. Confirm the Ingenium API is reachable, then try again.",
      };
  }
}

export function createBlockedReason(opts: {
  busy: boolean;
  authEnabled: boolean;
  hasBrowserKey: boolean;
}): string | null {
  if (opts.busy) return "Wait for the current step to finish.";
  if (!opts.authEnabled) return "Turn on API auth before creating keys.";
  if (!opts.hasBrowserKey) return "Save a browser key first, or generate the first key with bootstrap.";
  return null;
}

export function settingsSessionBadge(step: SettingsStepIndex): {
  label: string;
  variant: "default" | "warning" | "success" | "info" | "danger";
} {
  const labels = ["Status", "Keys", "Audit"] as const;
  const i = Math.max(1, Math.min(3, step)) - 1;
  const variants = ["default", "info", "success"] as const;
  return { label: labels[i], variant: variants[i] };
}

/** Alias used by the SettingsStateGuide component. */
export type SettingsStateGuide = SettingsGuide;
