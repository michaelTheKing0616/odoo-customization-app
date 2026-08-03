/** Normalize scanned barcode/QR payload for Odoo char fields. */
export function normalizeScanValue(raw: string): string {
  return String(raw ?? "").trim();
}

export function scanFindDomain(field: string, value: string): [string, string, string] {
  return [field, "=", normalizeScanValue(value)];
}
