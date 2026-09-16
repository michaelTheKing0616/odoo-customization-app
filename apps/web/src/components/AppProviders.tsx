"use client";

import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { UpgradeProvider } from "@/lib/upgrade-context";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <UpgradeProvider>{children}</UpgradeProvider>
    </ThemeProvider>
  );
}
