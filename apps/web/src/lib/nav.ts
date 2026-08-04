import type { IconComponent } from "@/components/ui/icons";
import {
  IconAccess,
  IconApprovals,
  IconAutomations,
  IconBulk,
  IconConfig,
  IconConnection,
  IconCron,
  IconExpert,
  IconFields,
  IconHousekeeping,
  IconIdGenerator,
  IconImport,
  IconMenus,
  IconModels,
  IconReports,
  IconCodeStudio,
  IconSnapshots,
  IconViews,
  IconWebsite,
} from "@/components/ui/icons";

export type NavGroupId =
  | "overview"
  | "build"
  | "ai"
  | "data"
  | "operate"
  | "govern";

export type NavItem = {
  id: string;
  label: string;
  href: (connectionId: string) => string;
  group: NavGroupId;
  icon: IconComponent;
  /** Odoo module name — locks nav when not in installed_modules_sample */
  moduleKey?: string;
  /** Capability id from connection.capabilities.supported — when set, item locks if unsupported */
  capabilityKey?: string;
  /** When false, hide until feature ships */
  shipped?: boolean;
  gatingTitle?: string;
  gatingWhy?: string;
  gatingOptions?: string[];
};

export const NAV_GROUPS: { id: NavGroupId; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "build", label: "Build" },
  { id: "ai", label: "AI" },
  { id: "data", label: "Data" },
  { id: "operate", label: "Operate" },
  { id: "govern", label: "Govern" },
];

export const NAV_ITEMS: NavItem[] = [
  {
    id: "overview",
    label: "Overview",
    href: (id) => `/connections/${id}`,
    group: "overview",
    icon: IconConnection,
    shipped: true,
  },
  {
    id: "builder",
    label: "Models & Fields",
    href: (id) => `/connections/${id}/builder`,
    group: "build",
    icon: IconFields,
    shipped: true,
  },
  {
    id: "designer",
    label: "View Designer",
    href: (id) => `/connections/${id}/designer`,
    group: "build",
    icon: IconViews,
    capabilityKey: "view_inject_inherit",
    shipped: true,
    gatingTitle: "View designer needs inherit injection",
    gatingWhy: "This Odoo version or edition does not expose safe view inherit injection.",
    gatingOptions: ["Export as a module instead", "Upgrade Odoo major", "Use staging"],
  },
  {
    id: "menus",
    label: "Menus",
    href: (id) => `/connections/${id}/menus`,
    group: "build",
    icon: IconMenus,
    shipped: true,
  },
  {
    id: "website",
    label: "Website",
    href: (id) => `/connections/${id}/website`,
    group: "build",
    icon: IconWebsite,
    moduleKey: "website",
    shipped: true,
    gatingTitle: "Website module required",
    gatingWhy: "Page content editing needs the Odoo website module installed on this instance.",
    gatingOptions: ["Install website in Odoo Apps", "Use Odoo's native website editor"],
  },
  {
    id: "automations",
    label: "Automations",
    href: (id) => `/connections/${id}/automations`,
    group: "build",
    icon: IconAutomations,
    capabilityKey: "base_automation_safe_triggers",
    shipped: true,
    gatingTitle: "Automations are limited on this instance",
    gatingWhy: "Safe automation triggers are not available for this Odoo major or edition.",
    gatingOptions: ["Export server actions in a module", "Use a supported Odoo version"],
  },
  {
    id: "approvals",
    label: "Approvals",
    href: (id) => `/connections/${id}/approvals`,
    group: "build",
    icon: IconApprovals,
    shipped: true,
  },
  {
    id: "reports",
    label: "Reports",
    href: (id) => `/connections/${id}/reports`,
    group: "build",
    icon: IconReports,
    shipped: true,
  },
  {
    id: "code-studio",
    label: "Code Studio",
    href: (id) => `/connections/${id}/code-studio`,
    group: "build",
    icon: IconCodeStudio,
    shipped: true,
  },
  {
    id: "access",
    label: "Access",
    href: (id) => `/connections/${id}/access`,
    group: "build",
    icon: IconAccess,
    shipped: true,
  },
  {
    id: "wizard",
    label: "Draft Studio",
    href: (id) => `/connections/${id}/wizard`,
    group: "ai",
    icon: IconExpert,
    shipped: true,
  },
  {
    id: "modulespec",
    label: "ModuleSpec",
    href: (id) => `/connections/${id}/modulespec`,
    group: "ai",
    icon: IconModels,
    shipped: true,
  },
  {
    id: "projects",
    label: "Projects",
    href: (id) => `/connections/${id}/projects`,
    group: "ai",
    icon: IconModels,
    shipped: true,
  },
  {
    id: "expert",
    label: "Odoo Expert",
    href: (id) => `/connections/${id}?expert=1`,
    group: "ai",
    icon: IconExpert,
    shipped: true,
  },
  {
    id: "import",
    label: "Import",
    href: (id) => `/connections/${id}/import`,
    group: "data",
    icon: IconImport,
    shipped: true,
  },
  {
    id: "id-generator",
    label: "ID Generator",
    href: (id) => `/connections/${id}/id-generator`,
    group: "data",
    icon: IconIdGenerator,
    shipped: true,
  },
  {
    id: "bulk-suite",
    label: "Bulk Suite",
    href: (id) => `/connections/${id}/bulk-suite`,
    group: "operate",
    icon: IconBulk,
    shipped: true,
  },
  {
    id: "power-ops",
    label: "Power Ops",
    href: (id) => `/connections/${id}/power-ops`,
    group: "operate",
    icon: IconBulk,
    shipped: true,
  },
  {
    id: "cron-manager",
    label: "Cron Manager",
    href: (id) => `/connections/${id}/cron-manager`,
    group: "operate",
    icon: IconCron,
    shipped: true,
  },
  {
    id: "housekeeping",
    label: "Housekeeping",
    href: (id) => `/connections/${id}/housekeeping`,
    group: "operate",
    icon: IconHousekeeping,
    shipped: true,
  },
  {
    id: "reminders",
    label: "Reminders",
    href: (id) => `/connections/${id}/reminders`,
    group: "operate",
    icon: IconCron,
    shipped: true,
  },
  {
    id: "script-runner",
    label: "Script Runner",
    href: (id) => `/connections/${id}/script-runner`,
    group: "operate",
    icon: IconCodeStudio,
    shipped: true,
  },
  {
    id: "journal",
    label: "Snapshots & Journal",
    href: (id) => `/connections/${id}/journal`,
    group: "govern",
    icon: IconSnapshots,
    shipped: true,
  },
  {
    id: "config",
    label: "Config",
    href: (id) => `/connections/${id}/config`,
    group: "govern",
    icon: IconConfig,
    shipped: true,
  },
];

export function navItemLocked(
  item: NavItem,
  supported: string[] | undefined,
  installedModules?: string[] | undefined,
): boolean {
  if (item.moduleKey) {
    if (!installedModules?.length) return true;
    if (!installedModules.includes(item.moduleKey)) return true;
  }
  if (!item.capabilityKey) return false;
  if (!supported) return true;
  return !supported.includes(item.capabilityKey);
}

export function breadcrumbForPath(connectionId: string, pathname: string) {
  const base = `/connections/${connectionId}`;
  const item = NAV_ITEMS.find((n) => n.href(connectionId) === pathname);
  const crumbs = [
    { label: "Connections", href: "/connect" },
    { label: "Overview", href: base },
  ];
  if (item && item.id !== "overview") {
    crumbs.push({ label: item.label, href: pathname });
  }
  return crumbs;
}
