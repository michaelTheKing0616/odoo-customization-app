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
        "This secret is for Odoo external RPC (XML-RPC / JSON-RPC) so Ingenium can talk to your database — not a Cursor MCP server key or Model Context Protocol connector. Online often rejects the website login password for RPC; create an API key under Preferences → Account Security → New API Key.",
    };
  }
  if (kind === "odoo_sh") {
    return {
      label: "Password or API key",
      hint:
        "Odoo external RPC credential (XML-RPC / JSON-RPC) for Ingenium — not a Cursor MCP connector. Login password usually works on Odoo.sh; an API key is safer for automation.",
    };
  }
  return {
    label: "Password or API key",
    hint:
      "Odoo external RPC credential (XML-RPC / JSON-RPC) for Ingenium — not a Cursor MCP connector. On-prem / Community: login password is usually enough; prefer an API key for production.",
  };
}

export function hostCapabilityBullets(kind: HostingKind): string[] {
  if (kind === "online") {
    return [
      "Views, fields, automations, and Config recipes via public ORM — supported.",
      "Custom Python modules cannot be installed on Online — use Odoo.sh or on-prem for that.",
      "Prefer Odoo API keys for XML-RPC/JSON-RPC (not Cursor MCP); strip /odoo from browser URLs.",
    ];
  }
  if (kind === "odoo_sh") {
    return [
      "Full RPC customization path plus Git-based module deploy.",
      "Use staging branches before promote to production.",
      "Password or Odoo API key both work for XML-RPC/JSON-RPC (not Cursor MCP).",
    ];
  }
  if (kind === "self_hosted") {
    return [
      "Fullest surface: sandbox → promote, filesystem modules, Docker majors.",
      "Community and Enterprise both connect the same way; EE-only features stay capability-gated.",
      "Login password usually enough for RPC; Odoo API keys recommended for prod (not Cursor MCP).",
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
        ? "RPC secret entered — Online works best with an Odoo API key if password auth is denied."
        : "Create an Odoo API key for external RPC (Preferences → Account Security). Not a Cursor MCP key — website password often fails for Online RPC."
      : secretOk
        ? "RPC secret entered — Odoo password or API key is fine (not Cursor MCP)."
        : "Enter your Odoo login password or an Odoo API key for XML-RPC/JSON-RPC (not a Cursor MCP connector).";

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
      `${message} — On Odoo Online, create an Odoo API key for external RPC (XML-RPC / JSON-RPC) under Preferences → Account Security, then paste it here. ` +
      "This is not a Cursor MCP / Model Context Protocol connector key. Website passwords are often rejected for RPC (especially with 2FA)."
    );
  }
  if (kind === "odoo_sh") {
    return (
      `${message} — Check database name and user. Odoo password or API key works for XML-RPC/JSON-RPC on Odoo.sh (not Cursor MCP).`
    );
  }
  return `${message} — Confirm database, user, and Odoo password or API key for external RPC (not a Cursor MCP key).`;
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
      body: "Odoo shows the key only once. Copy it, return to Ingenium, and paste it into the secret field. This Odoo external-RPC key lets Ingenium call XML-RPC/JSON-RPC — it is not a Cursor MCP server key or Model Context Protocol connector.",
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

/** Default Label on the Connect form (local-dev preset). */
export const DEFAULT_CONNECTION_LABEL = "Local Odoo 19";

/** True when Label still looks auto-managed (untouched default or mirrors current DB). */
export function connectionLabelFollowsDb(label: string, currentDb: string): boolean {
  const t = (label || "").trim();
  return t === "" || t === DEFAULT_CONNECTION_LABEL || t === (currentDb || "").trim();
}

/** If Label is still auto, mirror nextDb; otherwise keep the user's Label. */
export function nextConnectionLabel(
  label: string,
  currentDb: string,
  nextDb: string,
): string {
  if (!connectionLabelFollowsDb(label, currentDb)) return label;
  const db = (nextDb || "").trim();
  return db || DEFAULT_CONNECTION_LABEL;
}

