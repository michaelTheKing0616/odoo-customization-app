/** Client-side mirrors of odoo_client hosting helpers (connect UX). */

export type HostingKind = "online" | "odoo_sh" | "self_hosted" | "unknown";

export function normalizeOdooBaseUrl(url: string): string {
  let raw = (url || "").trim();
  if (!raw) return raw;
  if (!raw.includes("://")) raw = `https://${raw}`;
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    return raw.replace(/\/+$/, "");
  }
  let path = parsed.pathname.replace(/\/+$/, "") || "";
  const junkExact = [
    "/xmlrpc/2/common",
    "/xmlrpc/2/object",
    "/xmlrpc/2",
    "/xmlrpc",
    "/jsonrpc",
    "/web/login",
    "/web/session/authenticate",
    "/web",
    "/odoo",
    "/discuss",
    "/odoo/discuss",
  ];
  let guard = 0;
  while (path && guard++ < 12) {
    const lower = path.toLowerCase();
    let stripped = false;
    for (const junk of [...junkExact].sort((a, b) => b.length - a.length)) {
      if (lower === junk || lower.endsWith(junk)) {
        path = path.slice(0, -junk.length).replace(/\/+$/, "");
        stripped = true;
        break;
      }
    }
    if (!stripped) {
      for (const prefix of ["/odoo/", "/web/"]) {
        const idx = lower.indexOf(prefix.replace(/\/$/, ""));
        if (lower.startsWith(prefix) || idx === 0) {
          path = path.slice(0, Math.max(0, lower.indexOf(prefix.replace(/\/$/, "")))).replace(/\/+$/, "");
          stripped = true;
          break;
        }
      }
    }
    if (!stripped) break;
  }
  parsed.pathname = path || "/";
  parsed.search = "";
  parsed.hash = "";
  return parsed.toString().replace(/\/$/, "").replace(/\/$/, "");
}

export function detectHostingKind(url: string): HostingKind {
  let host = "";
  try {
    host = new URL(normalizeOdooBaseUrl(url)).hostname.toLowerCase();
  } catch {
    return "unknown";
  }
  if (!host) return "unknown";
  if (
    host === "127.0.0.1" ||
    host === "localhost" ||
    host === "0.0.0.0" ||
    host === "host.docker.internal" ||
    host.endsWith(".local")
  ) {
    return "self_hosted";
  }
  if (host === "odoo.sh" || host.endsWith(".odoo.sh") || host.includes("odoo.sh")) {
    return "odoo_sh";
  }
  if (host === "odoo.com" || host.endsWith(".odoo.com")) {
    return "online";
  }
  return "self_hosted";
}

export function suggestDbFromUrl(url: string): string | null {
  if (detectHostingKind(url) !== "online") return null;
  try {
    const host = new URL(normalizeOdooBaseUrl(url)).hostname.toLowerCase();
    if (!host.endsWith(".odoo.com")) return null;
    const label = host.slice(0, -".odoo.com".length);
    if (!label || label.includes(".")) return null;
    return label;
  } catch {
    return null;
  }
}

export function hostingHint(kind: HostingKind): string | null {
  if (kind === "online") {
    return "Odoo Online detected — use https://<db>.odoo.com (no /odoo path), database = subdomain, and an API key from Settings → Users → API Keys.";
  }
  if (kind === "odoo_sh") {
    return "Odoo.sh detected — use the project URL root (no /odoo). Branch/staging URLs still speak XML-RPC/JSON-RPC at the root.";
  }
  return null;
}

/** Best-effort URL to open Odoo so the user can create an API key.
 *
 * Keys are always created *inside Odoo* (we cannot mint them in Ingenium).
 * Deep links vary by major/edition, so we open the authenticated web client
 * root; the in-app guide walks Preferences → Account Security → New API Key.
 */
export function odooApiKeyGuideUrl(rawUrl: string): string | null {
  const base = normalizeOdooBaseUrl(rawUrl);
  if (!base || !/^https?:\/\//i.test(base)) return null;
  const kind = detectHostingKind(base);
  // Online 17+ shell is often /odoo; classic /web still works as entry.
  if (kind === "online") {
    return `${base}/odoo`;
  }
  return `${base}/web`;
}

export function odooApiKeyDocsUrl(majorHint?: number | null): string {
  const major = majorHint && majorHint >= 16 && majorHint <= 19 ? majorHint : 19;
  return `https://www.odoo.com/documentation/${major}.0/developer/reference/external_api.html#api-keys`;
}

