"use client";

import { UpgradeProvider } from "@/lib/upgrade-context";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return <UpgradeProvider>{children}</UpgradeProvider>;
}
