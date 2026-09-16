import type { NavGroupId } from "@/lib/nav";

export const NAV_EXPANDED_STORAGE_KEY = "nav-groups-expanded-v2"; // bump: Operations expanded by default for Co-Pilot

export const DEFAULT_NAV_EXPANDED: Record<NavGroupId, boolean> = {
  overview: true,
  build: true,
  ai: true,
  data: false,
  operate: true, // Co-Pilot + ops tools visible without an extra click
  govern: false,
};

export function loadNavExpanded(): Record<NavGroupId, boolean> {
  if (typeof window === "undefined") return { ...DEFAULT_NAV_EXPANDED };
  try {
    const raw = localStorage.getItem(NAV_EXPANDED_STORAGE_KEY);
    if (!raw) return { ...DEFAULT_NAV_EXPANDED };
    return { ...DEFAULT_NAV_EXPANDED, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT_NAV_EXPANDED };
  }
}

export function saveNavExpanded(state: Record<NavGroupId, boolean>) {
  localStorage.setItem(NAV_EXPANDED_STORAGE_KEY, JSON.stringify(state));
}

export function isNavItemActive(
  pathname: string,
  href: string,
  itemId: string,
  search: string,
): boolean {
  if (itemId === "overview") {
    return pathname === href;
  }
  if (itemId === "expert") {
    return pathname === href.split("?")[0] && search.includes("expert=1");
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}
