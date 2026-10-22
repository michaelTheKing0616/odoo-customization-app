export const DOC_TYPES = [
  "coa",
  "bom",
  "product_catalog",
  "customer_list",
  "vendor_list",
  "price_list",
  "employee_roster",
  "opening_trial_balance",
  "inventory_count",
  "other",
] as const;

export type DocType = (typeof DOC_TYPES)[number];

const LABELS: Record<DocType, string> = {
  coa: "Chart of accounts",
  bom: "Bill of materials",
  product_catalog: "Product catalog",
  customer_list: "Customer list",
  vendor_list: "Vendor list",
  price_list: "Price list",
  employee_roster: "Employee roster",
  opening_trial_balance: "Opening trial balance",
  inventory_count: "Inventory count",
  other: "Other",
};

export function docTypeLabel(value: string): string {
  return LABELS[value as DocType] ?? value.replaceAll("_", " ");
}

export const DOC_TYPE_OPTIONS = DOC_TYPES.map((value) => ({
  value,
  label: LABELS[value],
}));
