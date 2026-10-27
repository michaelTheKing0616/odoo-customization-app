/**
 * UI-S-08 / UI-CONNECT Connect screen logic and copy.
 * Pure helpers. No React. Honesty for Observer default + API-key preference.
 * One teal primary: Add connection.
 */

export const PAGE_TITLE = "Connect your Odoo";
export const PAGE_DESCRIPTION =
  "URL, database, and Odoo API key or password for Odoo's API. Not a Cursor MCP connector. Credentials are encrypted at rest and verified before save.";
export const PRIMARY_CTA = "Add connection";
export const PRIMARY_CTA_BUSY = "Verifying…";

export const CONNECT_STEPS = ["Credentials", "Probe", "Summary"] as const;
export type ConnectStepLabel = (typeof CONNECT_STEPS)[number];
export type ConnectStepId = "credentials" | "probe" | "summary";

export type ConnectGuide = { title: string; why: string; next: string };

export type ConnectErrorContext =
  | "dns"
  | "tls"
  | "auth"
  | "unsupported"
  | "duplicate"
  | "network"
  | "two_factor"
  | "ip_blocked"
  | "db_missing"
  | "generic";

/** Strip em / en dashes from UI copy (playbook law 9). */
export function sanitizeConnectCopy(text: string): string {
  return text.replace(/[\u2014\u2013]/g, "-");
}

export function resolveConnectStep(opts: {
  step: 1 | 2 | 3;
  saving: boolean;
}): ConnectStepId {
  if (opts.step === 3) return "summary";
  if (opts.step === 2 || opts.saving) return "probe";
  return "credentials";
}

export function connectStepFromId(id: ConnectStepId): 1 | 2 | 3 {
  if (id === "summary") return 3;
  if (id === "probe") return 2;
  return 1;
}

/** Always-on honesty: Observer default + least privilege. */
export function connectHonestyGuide(): ConnectGuide {
  return {
    title: "New connections start in Observer",
    why: "Observer is read-only. Ingenium cannot exceed the Odoo user's rights. Use a dedicated least-privilege user, not your full admin account.",
    next: "Add the connection, then unlock write mode from the connection overview when you are ready to customize.",
  };
}


/** One-line Observer chrome (not a stacked what/why/next banner). */
export function connectObserverNote(): string {
  return "Starts in Observer (read-only). Unlock write mode from the connection overview when ready.";
}

/** Short API-key tip for Online chrome (inline, not a twin banner). */
export function connectSecretTip(isOnline: boolean): string | null {
  if (isOnline) {
    return "Online: prefer an Odoo API key under Preferences → Account Security. Website passwords often fail for RPC.";
  }
  return null;
}

/** Empty first-run guide (no saved connections yet). */
export function emptyConnectGuide(): ConnectGuide {
  return {
    title: "No saved connections yet",
    why: "A verified connection is the gate to App Studio, Projects, and the rest of the operate shell.",
    next: "Enter URL, database, username, and an Odoo API key (preferred) or password. Then Add connection.",
  };
}

/** API-key preference honesty (complements the field hint). */
export function connectApiKeyHonestyGuide(isOnline: boolean): ConnectGuide {
  if (isOnline) {
    return {
      title: "Odoo Online prefers an API key",
      why: "Website login passwords often fail for external RPC on Online, especially with 2FA. An Odoo API key under Preferences → Account Security is the reliable path.",
      next: "Open Odoo to create a key, paste it into the secret field, then Add connection. Do not use a Cursor MCP key.",
    };
  }
  return {
    title: "API key preferred over password",
    why: "A password works for many self-hosted and Odoo.sh databases. An Odoo API key is safer for long-lived automation and is still Odoo's API, not Cursor MCP.",
    next: "Paste an Odoo password or API key, then Add connection.",
  };
}

export function connectedGuide(opts: {
  serverVersion?: string | null;
  capsMessage?: string | null;
}): ConnectGuide {
  const versionBit = opts.serverVersion
    ? ` Detected ${opts.serverVersion}.`
    : "";
  const capsBit = opts.capsMessage ? ` ${opts.capsMessage}` : "";
  return {
    title: "You're connected",
    why: `Credentials verified and stored encrypted.${versionBit}${capsBit}`.trim(),
    next: "Open App Studio to describe an app (no live write yet), keep the draft in Projects, or browse Overview when you want the full map.",
  };
}

export const PROBE_STAGES = [
  "Reaching server…",
  "Checking version…",
  "Checking rights…",
] as const;

/** Cycle probe stage copy while verifying (UI-S-08). */
export function probeStageLabel(elapsedMs: number): string {
  const idx = Math.min(
    PROBE_STAGES.length - 1,
    Math.floor(Math.max(0, elapsedMs) / 900),
  );
  return PROBE_STAGES[idx];
}

export function classifyConnectError(message?: string | null): ConnectErrorContext {
  const m = (message || "").toLowerCase();
  if (/two.?factor|2fa|totp|mfa/.test(m)) return "two_factor";
  if (/\b403\b|forbidden|ip.*(blocked|not allowed|whitelist|allowlist)/.test(m)) return "ip_blocked";
  if (/database .*(does not exist|not found)|no database|db.*not found|keyerror.*db/.test(m)) return "db_missing";
  if (/enotfound|getaddrinfo|dns|name or service not known|nodename/.test(m)) {
    return "dns";
  }
  if (/tls|ssl|certificate|cert_|handshake|self.signed/.test(m)) {
    return "tls";
  }
  if (
    /auth|access denied|401|invalid.*(password|key|credentials)|wrong.*(password|login)/.test(
      m,
    )
  ) {
    return "auth";
  }
  if (/unsupported|major\s*(1[0-5]|≤\s*15)|version.*(too old|not supported)/.test(m)) {
    return "unsupported";
  }
  if (/duplicate|already exists|unique/.test(m)) {
    return "duplicate";
  }
  if (/timeout|econnrefused|econnreset|network|fetch failed|unreachable/.test(m)) {
    return "network";
  }
  return "generic";
}

export function connectErrorGuide(
  context: ConnectErrorContext | string,
  detail?: string | null,
): ConnectGuide {
  const ctx =
    typeof context === "string" &&
    ["dns", "tls", "auth", "unsupported", "duplicate", "network", "two_factor", "ip_blocked", "db_missing", "generic"].includes(
      context,
    )
      ? (context as ConnectErrorContext)
      : classifyConnectError(detail || context);

  const detailLine = (detail || "").trim();

  switch (ctx) {
    case "two_factor":
      return {
        title: "Two-step sign-in is on for this user",
        why: detailLine || "Odoo asks for a one-time code, which a password cannot answer.",
        next: "In Odoo, open your profile, Account Security, and create an API key. Paste the key here instead of the password.",
      };
    case "ip_blocked":
      return {
        title: "The server refused this connection",
        why: detailLine || "The Odoo host or its firewall is blocking requests from Ingenium.",
        next: "Ask whoever hosts the database to allow outside API access, or add Ingenium's address to the allowed list, then try again.",
      };
    case "db_missing":
      return {
        title: "That database name was not found",
        why: detailLine || "The server is reachable, but it has no database with that name.",
        next: "Check the database name. On Odoo Online it is usually the first part of your web address.",
      };
    case "dns":
      return {
        title: "Could not reach that host",
        why: detailLine || "DNS lookup failed for the URL you entered.",
        next: "Check the hostname for typos. Use the site root (no /odoo path). Try again when the host resolves.",
      };
    case "tls":
      return {
        title: "TLS handshake failed",
        why: detailLine || "The certificate or TLS negotiation did not succeed.",
        next: "Confirm https vs http, fix the certificate on the Odoo host, then Add connection again.",
      };
    case "auth":
      return {
        title: "Authentication failed",
        why:
          detailLine ||
          "The database rejected the username or secret for external RPC.",
        next: "Fix the part named above, then save again. On Odoo Online, use an API key from Preferences → Account Security.",
      };
    case "unsupported":
      return {
        title: "This Odoo major is not supported yet",
        why: detailLine || "The probed major is below the supported range (16 experimental, 17-19 GA).",
        next: "Connect an Odoo 17-19 database, or a 16 instance if you accept experimental support.",
      };
    case "duplicate":
      return {
        title: "That connection already exists",
        why: detailLine || "A saved connection already uses this URL and database.",
        next: "Open the existing row below, or edit its label and secret instead of adding a duplicate.",
      };
    case "network":
      return {
        title: "Network error while probing",
        why: detailLine || "The probe could not complete a round trip to Odoo.",
        next: "Check that Odoo is running and reachable from this machine, then Add connection again.",
      };
    default:
      return {
        title: "Could not save the connection",
        why: detailLine || "The probe or save step failed.",
        next: "Fix the URL, database, and secret, then Add connection again.",
      };
  }
}

export function hasEmOrEnDash(text: string): boolean {
  return /[\u2014\u2013]/.test(text);
}

/** Saved-connection paging. Mirrors GET /api/connections (default 50, max 200). */
export const CONNECTIONS_PAGE_DEFAULT = 50;
export const CONNECTIONS_PAGE_MAX = 200;
/** h-11. Virtuoso needs the same row height in pixels. */
export const SAVED_CONNECTION_ROW_PX = 44;
/** Extra rows Virtuoso may mount on each side of the viewport. */
export const SAVED_CONNECTION_OVERSCAN_MAX = 2;
export const SAVED_CONNECTIONS_VIEWPORT_PX = 440;

const LIMIT_DETAIL = "limit must be from 1 to 200";
const OFFSET_DETAIL = "offset must be a non-negative integer";
const SEARCH_DETAIL = "search must be at most 200 characters";
const GROUP_DETAIL = "group must be at most 80 characters";
const OVERSCAN_DETAIL = "overscan must be an integer from 0 to 2";
const VIEWPORT_DETAIL = "viewport and row height must be positive";

export type SavedConnectionRow = {
  id: string;
  name: string;
  url: string;
  db_name: string;
  group_label: string | null;
};

export type ConnectionsPageQuery = {
  limit?: number;
  offset?: number;
  search?: string;
  group?: string;
};

export type ConnectionsPageError = {
  ok: false;
  status: 422;
  detail: string;
};

export type ConnectionsQueryPlan = {
  ok: true;
  limit: number;
  offset: number;
  search: string;
  group: string;
  path: string;
};

export type ConnectionsPage<T> = {
  ok: true;
  items: T[];
  total: number;
  limit: number;
  offset: number;
  nextOffset: number | null;
  path: string;
};

type ResolvedPaging = {
  limit: number;
  offset: number;
  search: string;
  group: string;
};

function resolvePaging(query: ConnectionsPageQuery): ResolvedPaging | ConnectionsPageError {
  const limit = query.limit === undefined ? CONNECTIONS_PAGE_DEFAULT : query.limit;
  const offset = query.offset === undefined ? 0 : query.offset;
  if (!Number.isInteger(limit) || limit < 1 || limit > CONNECTIONS_PAGE_MAX) {
    return { ok: false, status: 422, detail: LIMIT_DETAIL };
  }
  if (!Number.isInteger(offset) || offset < 0) {
    return { ok: false, status: 422, detail: OFFSET_DETAIL };
  }
  const search = (query.search ?? "").trim();
  const group = (query.group ?? "").trim();
  if (search.length > 200) {
    return { ok: false, status: 422, detail: SEARCH_DETAIL };
  }
  if (group.length > 80) {
    return { ok: false, status: 422, detail: GROUP_DETAIL };
  }
  return { limit, offset, search, group };
}

function connectionsListPath(paging: ResolvedPaging): string {
  const params = new URLSearchParams();
  params.set("limit", String(paging.limit));
  params.set("offset", String(paging.offset));
  if (paging.search) params.set("q", paging.search);
  if (paging.group) params.set("group", paging.group);
  return `/api/connections?${params.toString()}`;
}

function toConnectionsQueryPlan(
  query: ConnectionsPageQuery,
): ConnectionsQueryPlan | ConnectionsPageError {
  const paging = resolvePaging(query);
  if ("status" in paging) return paging;
  return { ok: true, ...paging, path: connectionsListPath(paging) };
}

function matchesGroup(row: SavedConnectionRow, group: string): boolean {
  if (!group) return true;
  return row.group_label === group;
}

function matchesSearch(row: SavedConnectionRow, search: string): boolean {
  if (!search) return true;
  const needle = search.toLowerCase();
  const fields = [row.name, row.url, row.db_name, row.group_label ?? ""];
  return fields.some((field) => field.toLowerCase().includes(needle));
}

export function applyConnectionsQuery<T extends SavedConnectionRow>(
  rows: readonly T[],
  query: ConnectionsPageQuery = {},
): ConnectionsPage<T> | ConnectionsPageError {
  const plan = toConnectionsQueryPlan(query);
  if (!plan.ok) return plan;
  const filtered = rows.filter(
    (row) => matchesGroup(row, plan.group) && matchesSearch(row, plan.search),
  );
  const items = filtered.slice(plan.offset, plan.offset + plan.limit);
  const next = plan.offset + items.length;
  return {
    ok: true,
    items,
    total: filtered.length,
    limit: plan.limit,
    offset: plan.offset,
    nextOffset: next < filtered.length ? next : null,
    path: plan.path,
  };
}

/**
 * A new search or group starts at the first page. Keeping the old offset
 * can land past the new matches and look like a frozen empty list.
 */
export function nextSavedConnectionsQuery(
  current: ConnectionsPageQuery,
  change: ConnectionsPageQuery,
): ConnectionsQueryPlan | ConnectionsPageError {
  const filterChanged = change.search !== undefined || change.group !== undefined;
  return toConnectionsQueryPlan({
    limit: change.limit !== undefined ? change.limit : current.limit,
    offset: change.offset !== undefined ? change.offset : filterChanged ? 0 : current.offset,
    search: change.search !== undefined ? change.search : current.search,
    group: change.group !== undefined ? change.group : current.group,
  });
}

export function clampSavedListOverscan(
  requested: number,
): { ok: true; overscan: number } | ConnectionsPageError {
  if (!Number.isInteger(requested) || requested < 0 || requested > SAVED_CONNECTION_OVERSCAN_MAX) {
    return { ok: false, status: 422, detail: OVERSCAN_DETAIL };
  }
  return { ok: true, overscan: requested };
}

export function savedConnectionMountCap(
  viewportHeight: number,
  rowPx: number,
  overscanItems: number,
): { ok: true; mountAtMost: number } | ConnectionsPageError {
  if (!(viewportHeight > 0) || !(rowPx > 0)) {
    return { ok: false, status: 422, detail: VIEWPORT_DETAIL };
  }
  const overscan = clampSavedListOverscan(overscanItems);
  if (!overscan.ok) return overscan;
  const visible = Math.ceil(viewportHeight / rowPx);
  // Numeric Virtuoso overscan is applied on both sides of the viewport.
  return { ok: true, mountAtMost: visible + overscan.overscan * 2 };
}

export function savedConnectionsViewportPx(viewportHeight: number): number {
  const cap = savedConnectionMountCap(
    viewportHeight,
    SAVED_CONNECTION_ROW_PX,
    SAVED_CONNECTION_OVERSCAN_MAX,
  );
  return cap.ok ? viewportHeight : SAVED_CONNECTIONS_VIEWPORT_PX;
}
