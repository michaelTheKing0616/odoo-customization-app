/** Pure Connect checklist helpers (consultant-speed connect UX). */

import type { HostingKind } from "./odoo-hosting";
import {
  detectHostingKind,
  normalizeOdooBaseUrl,
  suggestDbFromUrl,
} from "./odoo-hosting";

export type ChecklistStepId =
  | "url"
  | "hosting"
  | "database"
  | "username"
  | "secret"
  | "verify";

export type ChecklistStep = {
  id: ChecklistStepId;
  label: string;
  detail: string;
  done: boolean;
  emphasis?: "default" | "warn";
};

export type ConnectChecklistInput = {
  url: string;
  dbName: string;
  username: string;
  password: string;
  /** True after a successful probe/save in this session. */
  verified?: boolean;
};

export function credentialFieldCopy(kind: HostingKind): {
  label: string;
  hint: string;
} {
  if (kind === "online") {
    return {
      label: "API key (preferred) or password",
      hint:
        "Odoo Online often rejects the website login password for external RPC — create an API key under Settings → Users → API Keys. Password may still work on some tenants; if auth fails, switch to a key.",
    };
  }
  if (kind === "odoo_sh") {
    return {
      label: "Password or API key",
      hint:
        "Login password usually works on Odoo.sh. An API key is still safer for automation and least privilege.",
    };
  }
  return {
    label: "Password or API key",
    hint:
      "On-prem / Community: login password is usually enough. Prefer an API key for production integrations.",
  };
}

export function hostCapabilityBullets(kind: HostingKind): string[] {
  if (kind === "online") {
    return [
      "Views, fields, automations, and Config recipes via public ORM — supported.",
      "Custom Python modules cannot be installed on Online — use Odoo.sh or on-prem for that.",
      "Prefer API keys for RPC; strip /odoo from browser URLs.",
    ];
  }
  if (kind === "odoo_sh") {
    return [
      "Full RPC customization path plus Git-based module deploy.",
      "Use staging branches before promote to production.",
      "Password or API key both accepted by RPC in typical setups.",
    ];
  }
  if (kind === "self_hosted") {
    return [
      "Fullest surface: sandbox → promote, filesystem modules, Docker majors.",
      "Community and Enterprise both connect the same way; EE-only features stay capability-gated.",
      "Login password is usually enough; API keys recommended for prod.",
    ];
  }
  return [
    "We will detect hosting after you enter a URL.",
    "Supported majors are probed at connect — we do not hard-ceiling on a single Odoo version.",
  ];
}

export function buildConnectChecklist(input: ConnectChecklistInput): {
  kind: HostingKind;
  steps: ChecklistStep[];
  completed: number;
  total: number;
} {
  const kind = detectHostingKind(input.url);
  const normalized = normalizeOdooBaseUrl(input.url);
  const urlOk = Boolean(normalized && /^https?:\/\//i.test(normalized));
  const suggested = suggestDbFromUrl(input.url);
  const dbOk = Boolean(input.dbName.trim());
  const dbMatchesSuggest =
    !suggested || input.dbName.trim() === suggested || kind !== "online";
  const userOk = Boolean(input.username.trim());
  const secretOk = Boolean(input.password.trim());
  const verified = Boolean(input.verified);

  const secretDetail =
    kind === "online"
      ? secretOk
        ? "Secret entered — Online works best with an API key if password auth is denied."
        : "Create an API key (Settings → Users → API Keys). Website password often fails for Online RPC."
      : secretOk
        ? "Secret entered — password or API key is fine on this host."
        : "Enter your Odoo login password or an API key.";

  const steps: ChecklistStep[] = [
    {
      id: "url",
      label: "Base URL",
      detail: urlOk
        ? `Using ${normalized}`
        : "Paste the site root (we strip /odoo and deep links).",
      done: urlOk,
    },
    {
      id: "hosting",
      label: "Hosting detected",
      detail:
        kind === "online"
          ? "Odoo Online / SaaS"
          : kind === "odoo_sh"
            ? "Odoo.sh"
            : kind === "self_hosted"
              ? "Self-hosted / on-prem / custom domain"
              : "Enter a URL to detect Online, Odoo.sh, or on-prem",
      done: kind !== "unknown" && urlOk,
    },
    {
      id: "database",
      label: "Database",
      detail: !dbOk
        ? kind === "online"
          ? suggested
            ? `Suggested from subdomain: ${suggested}`
            : "Online DB is usually the subdomain (acme for acme.odoo.com)."
          : "Enter the PostgreSQL / Odoo database name."
        : dbMatchesSuggest
          ? `Database “${input.dbName.trim()}”`
          : `You entered “${input.dbName.trim()}” — Online subdomain suggests “${suggested}”.`,
      done: dbOk,
      emphasis: dbOk && !dbMatchesSuggest ? "warn" : "default",
    },
    {
      id: "username",
      label: "Login email / user",
      detail: userOk
        ? input.username.trim()
        : "Use the Odoo user email (not the DB owner OS user).",
      done: userOk,
    },
    {
      id: "secret",
      label: kind === "online" ? "API key or password" : "Password or API key",
      detail: secretDetail,
      done: secretOk,
      emphasis: kind === "online" && !secretOk ? "warn" : "default",
    },
    {
      id: "verify",
      label: "Verify & save",
      detail: verified
        ? "Probe succeeded — connection is ready."
        : "Save connection to probe version, edition, and capabilities.",
      done: verified,
    },
  ];

  const completed = steps.filter((s) => s.done).length;
  return { kind, steps, completed, total: steps.length };
}

export function formatAuthFailureHint(kind: HostingKind, message: string): string {
  const lower = (message || "").toLowerCase();
  const authish =
    lower.includes("auth") ||
    lower.includes("access denied") ||
    lower.includes("401") ||
    lower.includes("invalid") ||
    lower.includes("password");
  if (!authish) return message;
  if (kind === "online") {
    return (
      `${message} — On Odoo Online, create an API key (Settings → Users → API Keys) and paste it in the secret field. ` +
      "Website passwords are often rejected for external RPC (especially with 2FA)."
    );
  }
  if (kind === "odoo_sh") {
    return (
      `${message} — Check database name and user. Password usually works on Odoo.sh; an API key also works.`
    );
  }
  return `${message} — Confirm database, user, and password (or API key).`;
}

export type ApiKeyGuideStep = {
  title: string;
  body: string;
};

/** Numbered walkthrough — key is created on Odoo; Ingenium only receives it. */
export function apiKeyGuideSteps(kind: HostingKind): ApiKeyGuideStep[] {
  const where =
    kind === "online"
      ? "In the Odoo Online tab that opens"
      : kind === "odoo_sh"
        ? "In the Odoo.sh database tab that opens"
        : "In your Odoo web client tab that opens";
  return [
    {
      title: "Open Odoo (signed in)",
      body: `${where}, sign in with the same user you will use in Ingenium if prompted.`,
    },
    {
      title: "Open Preferences",
      body: "Click your avatar / user menu (top-right) → Preferences (or My Profile).",
    },
    {
      title: "Account Security → New API Key",
      body: "Open the Account Security tab → New API Key. Name it e.g. “Ingenium”, confirm your password if asked.",
    },
    {
      title: "Copy once → paste here",
      body: "Odoo shows the key only once. Copy it, return to Ingenium, and paste it into the secret field (not the website password).",
    },
  ];
}

export function shouldEmphasizeApiKeyGuide(kind: HostingKind, errorMessage?: string | null): boolean {
  if (kind === "online") return true;
  const lower = (errorMessage || "").toLowerCase();
  return (
    lower.includes("auth") ||
    lower.includes("access denied") ||
    lower.includes("api key") ||
    lower.includes("password") ||
    lower.includes("401")
  );
}

