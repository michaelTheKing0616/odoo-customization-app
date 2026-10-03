/**
 * Mirrors `packages/odoo-client/.../version_table.py` `native_mcp_present`.
 * Community images have no ai* modules; native MCP is absent.
 */
export function nativeMcpPresent(moduleNames: readonly string[]): boolean {
  return moduleNames.some((name) => name.startsWith("ai"));
}

/** Typical Community 20 module list (no ai*). Native MCP must read absent. */
export const COMMUNITY20_SAMPLE_MODULES = [
  "base",
  "web",
  "sale",
  "account",
  "stock",
] as const;
