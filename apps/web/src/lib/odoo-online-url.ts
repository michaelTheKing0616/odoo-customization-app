/** True for an Odoo Online address (https://<db>.odoo.com), never for odoo.sh or self-hosted. */
export function isOdooOnlineUrl(url?: string | null): boolean {
  try {
    const host = new URL(String(url || "")).hostname.toLowerCase();
    return host.endsWith(".odoo.com") && !host.endsWith(".odoo.sh");
  } catch {
    return false;
  }
}

/** Odoo's Apps screen for a database address (strips a trailing /odoo or /web path). */
export function odooAppsUrl(url?: string | null): string {
  const base = String(url || "").trim().replace(/\/+$/, "").replace(/\/(odoo|web)$/, "");
  return base ? `${base}/odoo/apps` : "";
}
