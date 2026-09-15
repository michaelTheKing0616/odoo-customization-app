"use client";

import { ThemeProvider } from "@/components/theme/ThemeProvider";

export default function PresenterOverlayLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ThemeProvider>
      <div className="min-h-screen bg-background text-ink">{children}</div>
    </ThemeProvider>
  );
}
