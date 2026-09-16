import type { Metadata } from "next";
import "./globals.css";
import { AppProviders } from "@/components/AppProviders";
import { DragAutoScroll } from "@/components/DragAutoScroll";
import { ThemeScript } from "@/components/theme/ThemeScript";

export const metadata: Metadata = {
  title: "Ingenium — No-code Odoo customization for Community",
  description:
    "Ingenium: Studio-class customization for Odoo Community. Connect any instance, customize safely, export real modules.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <ThemeScript />
      </head>
      <body
        className="min-h-screen antialiased bg-background text-ink"
        suppressHydrationWarning
      >
        <AppProviders>
          <DragAutoScroll />
          {children}
        </AppProviders>
      </body>
    </html>
  );
}
